"""Read-only evaluation of v2 changes; records AI findings without human signoff."""
import csv
import hashlib
import json
from pathlib import Path

from contract_v1 import make_rag_input, validate_rag_input, validate_test_case

BASE = Path(__file__).parent
DIFF = BASE / 'reviews/independent_120_v2_final_pending_diff.csv'
SOURCE = BASE / 'datasets/independent_120_v2_behavior_pending_review.jsonl'
OUT = BASE / 'reviews/independent_120_v2_ai_change_review.csv'
SUMMARY = BASE / 'reviews/independent_120_v2_ai_change_review.json'

# Review of what changed, not a substitute for checking the visual layout of
# every PDF table or a user's signature. These concerns need a source-page fix.
ISSUES = {
 'I120-T002': ('source_conflict', '表10.10.3 原页的瓶颈设施最大等待人数评价范围是“换乘路径端部设施（站台、楼扶梯）”；题干、F4、参考答案写作“沿路设施”。须修正题干、F4、答案和证据摘录并重新审核。'),
 'I120-N015': ('question_scope_conflict', '题干要求“现浇和装配式”分别给值，但原文及F2只写“防水混凝土”与装配式钢筋混凝土结构；不能把4×10^-12直接说成专属现浇值。须收窄问法或核实另有原文依据。'),
 'I120-T009': ('evidence_gap', 'F3“任何工况下站台面不应高于客室地板面”列为必答，但对应证据摘录只记录两个数值和跨页信息；须核原页并补直接支持该条的证据或取消必答。'),
 'I120-T007': ('evidence_gap', 'F4 中“车辆低于运行面以下部分且无安装设备”的适用条件未包含于该事实的证据摘录；原表条件必须核对后补入摘录。'),
 'I120-T011': ('question_scope_conflict', '题干只问两种曲线半径的加宽值，F3额外要求单线/双线的加宽位置；须裁定是否作为必答事实，或调整题干。'),
 'I120-T015': ('question_scope_conflict', '题干只问昼夜限值，F3额外要求未达标时的降噪措施；须裁定是否作为必答事实，或调整题干。'),
 'I120-Q014': ('clarification_overreach', '必需字段中的“适用的表注或括号标示条件”并非必然独立的项目输入；应先按原表确认具体哪一个条件会改变所问行列，再设为必问。'),
 'I120-Q019': ('clarification_overreach', '“所指支架位置”缺明确可问条件，可能与水平/垂直间距重复；须按跨页表原列名核定必需信息。'),
}


def main():
 rows = list(csv.DictReader(DIFF.open(encoding='utf-8-sig', newline='')))
 ids = [r['case_id'] for r in rows]
 cases = {c['case_id']: c for c in map(json.loads, SOURCE.read_text(encoding='utf-8').splitlines())}
 assert len(ids) == len(set(ids)) == 58 and len(cases) == 120
 assert set(ISSUES) <= set(ids)
 results = []
 for ident in ids:
  c = cases[ident]
  validate_test_case(c)
  validate_rag_input(make_rag_input(c))
  action = c['expected_action']
  if action == 'answer':
   old = c.get('numeric_constraints', [])
   new = c['numeric_constraints_v2']
   assert len(old) == len(new) and all(
    all(a[k] == b[k] for k in ('value', 'unit', 'comparison'))
    and a['condition'] in b['conditions']
    and b['fact_ids'] and all(fid in {x['fact_id'] for x in c['necessary_facts']} for fid in b['fact_ids'])
    for a,b in zip(old,new)), ident
   for n in new:
    assert n['link_semantics'] == 'all_facts', ident
   scope = f'{len(new)}项数值与原标注值、单位、比较方向一致；事实ID非空，关联语义all_facts'
  elif action == 'refuse':
   ann = c['refusal_annotation_v2']
   assert len(ann['missing_facts']) == 1 and c['supported_source_references'], ident
   assert '禁止无依据断言' in ann['allowed_explanation'][-1], ident
   scope = '缺失项目事实与禁止断言明确；规范前提来源保留且仅可选说明'
  else:
   ann = c['clarification_annotation_v2']
   assert ann['required_fields'] and not ann['branches'] and c['ambiguity_source_pages'], ident
   scope = '必问字段已拆分；后续分支页码仅诊断，未计入本轮证据'
  category, reason = ISSUES.get(ident, ('no_new_issue_in_change_review', '本轮变更比对未见新增冲突；仍须对照原PDF及新版评分项进行人工签核。'))
  results.append({'case_id':ident,'expected_action':action,'ai_change_review':category,
                  'comparison':scope,'finding':reason,'human_review_status':'pending_human_review'})
 with OUT.open('w', encoding='utf-8-sig', newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
 payload={'dataset_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
  'reviewed_case_count':len(results),'flagged_case_ids':list(ISSUES),
  'ai_change_review_only':True,'all_human_review_status':'pending_human_review',
  'pdf_page_visual_verification_complete':False,
  'protocol':'rag-eval.test-case.v2','public_input':'rag-eval.rag-input.v1',
  'findings':results}
 SUMMARY.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'rows':len(results),'flags':list(ISSUES),'dataset_sha256':payload['dataset_sha256']},ensure_ascii=False))

if __name__=='__main__':main()
