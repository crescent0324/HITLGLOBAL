"""Exercise nurse, head-nurse and caregiver workflows using disposable synthetic data."""
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
    directory=Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('只接受全新的虛構展示目錄。')
    provider=OfflineProvider()
    trace=[]
    with patch.object(socket,'create_connection',side_effect=AssertionError('External traffic forbidden')), \
         patch.object(provider,'generate',wraps=provider.generate) as generation:
        app=create_app(directory,provider=provider)
        clients={}
        def client(uid):
            if uid not in clients:
                c=app.test_client()
                token=c.get('/api/session').get_json()['csrf']
                body=c.post('/api/login',json={'username':uid,'password':DEMO_PASSWORD},headers={'X-CSRF-Token':token})
                assert body.status_code==200
                clients[uid]=(c,body.get_json()['csrf'])
            return clients[uid][0]
        def post(uid,path,payload,expected=200):
            c=client(uid)
            response=c.post(path,json=payload,headers={'X-CSRF-Token':clients[uid][1]})
            assert response.status_code==expected,(uid,path,response.status_code,response.get_json())
            return response.get_json()
        def monitor(**query):
            response=client('head_nurse').get('/api/case-monitor',query_string=query)
            assert response.status_code==200
            return response.get_json()
        def record(step,body):
            trace.append({'step':step,**body})

        incoming=post('nurse','/api/residents/R001/message',{'text':'虛構：家屬詢問聯絡安排，轉人工','channel':'demo_line','line_actor':'family'})
        cid=incoming['conversation_id']
        detail=client('nurse').get('/api/residents/R001',query_string={'conversation_id':cid}).get_json()
        case_id=detail['case']['id']
        payload={'case_id':case_id,'conversation_id':cid}
        def action(uid,name,extra=None,expected=200):
            return post(uid,'/api/residents/R001/case/'+name,payload|(extra or {}),expected)
        data=monitor()
        assert data['stats']['pending_cases']==1 and data['cases'][0]['due_at'] is None and data['stats']['overdue_cases'] is None
        record('護理長看到待接手，未設定期限不判定逾期',{'pending':1,'due_at':None,'overdue_cases':None})
        action('nurse','claim')
        action('nurse','handoff',{'summary':'虛構：已確認家屬服務詢問','next_action':'虛構：下一班確認安排後回覆','waiting_for':'虛構：等待確認時間','revision':0,'to_user':'nurse2'})
        data=monitor();item=data['cases'][0]
        assert item['owner']['id']=='nurse' and data['stats']['open_cases']==data['stats']['claimed_cases']==data['stats']['pending_handoffs']==1
        record('護理師提出交班，護理長看到同一件已接手案件',{'owner_id':'nurse','open_cases':1,'claimed_cases':1,'pending_handoffs':1})
        post('caregiver','/api/residents/R001/observation',{'observed_at':stamp(),'care_note':'虛構：記錄觀察，等待護理師評估','care_status':'尚未評估'})
        observation=client('caregiver').get('/api/residents/R001').get_json()
        assert set(observation)=={'resident','observations','role'}
        assert observation['observations'][0]['care_status']=='尚未評估'
        assert client('caregiver').get('/api/case-monitor').status_code==403
        action('caregiver','reply',{'text':'不得代回覆'},403)
        record('照服員保存未評估觀察，無主管 API 與家屬案件權限',{'observation':'尚未評估','monitor_status':403,'reply_status':403})
        request_id=item['handoff']['id']
        action('nurse2','accept_handoff',{'request_id':request_id})
        assert monitor()['cases'][0]['owner']['id']=='nurse2'
        action('nurse2','reply',{'text':'虛構：已確認聯絡安排，本機完成回覆'})
        action('nurse','resolve',{'note':'原責任帳號不能代結案'},403)
        action('nurse2','resolve',{'note':'虛構：家屬服務詢問已完成，保留完整交班歷程'})
        record('指定接班者接受、回覆、結案；舊責任帳號遭拒',{'owner_id':'nurse2','previous_owner_resolve_status':403})
        data=monitor(status='closed')
        assert len(data['cases'])==1 and data['cases'][0]['id']==case_id
        timeline=client('head_nurse').get(f'/api/case-monitor/{case_id}/timeline').get_json()
        assert {'handoff_proposed','handoff_accepted','case_reply','case_resolve'} <= {e['action'] for e in timeline['events']}
        assert timeline['case']['owner']['id']=='nurse2'
        action('head_nurse','reply',{'text':'主管不能代回覆'},403)
        record('護理長依責任與結案狀態查看進度及歷程，維持唯讀',{'case_id':case_id,'history_events':len(timeline['events']),'reply_status':403})
        assert client('admin').get('/api/bindings').status_code==200
        assert client('admin').get('/api/residents/R001').status_code==403
        post('admin','/api/backup',{},403)
        post('admin','/api/bindings',{'user_id':'head_nurse','resident_id':'R001','allowed':False})
        assert client('head_nurse').get(f'/api/case-monitor/{case_id}/timeline').status_code==404
        assert monitor(status='all')['cases']==[]
        record('IT 只管理授權；撤權立即影響護理長既有工作階段',{'it_detail_status':403,'it_backup_status':403,'revoked_timeline_status':404})
        post('admin','/api/bindings',{'user_id':'head_nurse','resident_id':'R001','allowed':True})
        app.extensions['care_service'].stop_worker()
        restored=create_app(directory,provider=provider)
        store=restored.extensions['care_store']
        from werkzeug.datastructures import MultiDict
        history=restored.extensions['care_monitor'].timeline(store.user('head_nurse'),case_id,MultiDict())
        assert history['case']['status']=='closed' and history['case']['owner']['id']=='nurse2'
        restored.extensions['care_service'].stop_worker()
        assert generation.call_count==0
        record('重新載入保留結案與責任 ID',{'status':'closed','operator_id':'nurse2'})
        return {'checked_at':stamp(),'result':'passed','mode':'synthetic_local_demo','model_calls':generation.call_count,
                'actual_line_sent':False,'trace':trace}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='care-monitor-demo-') as temporary:
        result=run_demo(Path(temporary)/'synthetic-data')
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text+'\n',encoding='utf-8')
    print(text)


if __name__=='__main__':
    main()
