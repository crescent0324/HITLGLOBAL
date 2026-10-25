"""Reproduce one synthetic family case locally, without LINE or model traffic."""
import argparse
import json
from pathlib import Path
import socket
import tempfile
from unittest.mock import patch
from app import create_app
from care_store import DEMO_PASSWORD, stamp
from integration import OfflineProvider


def run_demo(directory):
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('示範只使用全新的虛構資料目錄。')
    provider = OfflineProvider()
    trace = []
    with patch.object(socket, 'create_connection', side_effect=AssertionError('External traffic forbidden')):
        app = create_app(directory, provider=provider)
        client = app.test_client()
        csrf = client.get('/api/session').get_json()['csrf']
        cid = None
        case_id = None

        def post(path, payload, expected=200):
            response = client.post(path, json=payload, headers={'X-CSRF-Token': csrf})
            assert response.status_code == expected, (path, response.status_code, response.get_json())
            return response.get_json()

        def login(uid):
            nonlocal csrf
            body = post('/api/login', {'username': uid, 'password': DEMO_PASSWORD})
            csrf = body['csrf']

        def detail():
            response = client.get('/api/residents/R001', query_string={'conversation_id': cid})
            assert response.status_code == 200
            return response.get_json()

        def action(name, payload=None, expected=200):
            return post('/api/residents/R001/case/'+name,
                        {'case_id': case_id, 'conversation_id': cid, **(payload or {})}, expected)

        def record(step, body):
            case = body['case']
            trace.append({'step': step, 'state': body['state'], 'case_id': case_id,
                          'status': case['status'] if case else 'closed',
                          'operator_id': case['operator_id'] if case else None})

        login('nurse')
        incoming = post('/api/residents/R001/message', {
            'channel': 'demo_line', 'line_actor': 'family',
            'text': '轉人工：虛構家屬想確認聯絡安排，請由人員協助。'})
        assert incoming['actual_line_sent'] is False
        cid = incoming['conversation_id']
        body = detail();case_id = body['case']['id']
        assert body['case']['status'] == 'pending' and body['case']['operator_id'] is None
        record('家屬詢問建立待接手案件', body)

        action('claim');body = detail()
        assert body['case']['operator_id'] == 'nurse'
        record('護理師接手', body)
        post('/api/residents/R001/message', {'channel': 'demo_line', 'line_actor': 'family',
            'conversation_id': cid, 'text': '想了解日照服務'})
        body = detail()
        assert body['state'] == 'human_active' and body['case']['id'] == case_id
        record('一般新訊息保持人工責任', body)

        progress = {'summary': '虛構：已確認家屬詢問的聯絡安排',
                    'next_action': '接班者確認後於本機回覆', 'waiting_for': '等待接班', 'revision': 0}
        action('progress', progress)
        action('handoff', progress | {'revision': 1, 'to_user': 'nurse2'})
        body = detail();request_id = body['workflow']['handoff']['id']
        assert body['case']['operator_id'] == 'nurse'
        record('提出交班，原護理師持續負責', body)

        login('caregiver')
        response = client.get('/api/residents/R001', query_string={'conversation_id': cid})
        assert response.status_code == 403
        board = client.get('/api/board').get_json()
        assert board['work_queue'] == []
        assert set(client.get('/api/residents/R001').get_json()) == {'resident', 'observations', 'role'}
        action('reply', {'text': '照服員不得代為回覆'}, 403)
        trace.append({'step': '照服員仍可看照護紀錄，家屬對話及案件操作遭拒', 'status': '403 verified'})

        login('nurse2');action('accept_handoff', {'request_id': request_id})
        body = detail();assert body['case']['operator_id'] == 'nurse2'
        record('指定接班者確認接收', body)
        action('reply', {'text': '虛構：已記錄聯絡需求，這是本機示範回覆。'})
        body = detail()
        assert body['state'] == 'human_active'
        assert body['messages'][-1]['author'] == '接班護理師體驗帳號'
        record('新責任人於本機回覆', body)

        login('nurse');action('resolve', {'note': '原責任人不得再代為結案'}, 403)
        login('nurse2');action('resolve', {'note': '虛構：已於本機完成說明，沒有未完成的後續事項。'})
        body = detail()
        assert body['case'] is None and body['state'] == 'automatic'
        history = body['workflow']['history'][0]
        assert history['id'] == case_id and history['operator_id'] == 'nurse2'
        record('完成結案並保留處理歷史', body)
        other = next(t for t in body['conversations'] if t['contact_id'] == 'resident')
        response = client.get('/api/residents/R001', query_string={'conversation_id': other['id']})
        assert response.get_json()['messages'] == []
        assert provider.calls == []
        app.extensions['care_service'].stop_worker()

        restored = create_app(directory, provider=OfflineProvider())
        source = restored.extensions['care_service'].detail(cid)
        view = restored.extensions['care_workflow'].view(restored.extensions['care_store'].user('nurse2'), 'R001', source)
        assert source['case'] is None and view['history'][0]['id'] == case_id
        assert view['history'][0]['operator_id'] == 'nurse2'
        restored.extensions['care_service'].stop_worker()
        trace.append({'step': '重新載入後保留結案與責任 ID；另一聯絡人對話仍空白', 'status': 'verified'})
    return {'checked_at': stamp(), 'mode': 'synthetic_local_demo', 'actual_line_sent': False,
            'model_calls': 0, 'result': 'passed', 'trace': trace}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Optional JSON evidence file; never contains credentials.')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='care-family-mvp-') as temporary:
        result = run_demo(Path(temporary) / 'synthetic-data')
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text+'\n', encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
