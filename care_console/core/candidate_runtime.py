"""Load the exact candidate bytes and reject module-name collisions."""
from pathlib import Path
import hashlib,importlib.util,json,sys
BASE=Path(__file__).resolve().parent/'candidate'
MANIFEST=json.loads((BASE/'manifest.json').read_text(encoding='utf-8'))

def verify_candidate():
 for name,digest in MANIFEST['sha256'].items():
  if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=digest:
   raise RuntimeError('候選規則檔案已變動，請另存版本並更新整合紀錄。')
 return json.loads(json.dumps(MANIFEST))

def load(name,file):
 if name in sys.modules:
  if Path(sys.modules[name].__file__).resolve()!=(BASE/file).resolve():
   raise RuntimeError('候選模組名稱衝突，無法確認實際使用的治理版本。')
  return sys.modules[name]
 spec=importlib.util.spec_from_file_location(name,BASE/file)
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
 return module

verify_candidate()
RiskEngine=load('_hitl_v123_risk','risk_engine_v1_2_tw.py').RiskEngineV12TW
load('hitl_governance_v1','hitl_governance_v1.py')
Governance=load('_hitl_v123_governance','hitl_governance_v1_2.py').HITLGovernanceV12
