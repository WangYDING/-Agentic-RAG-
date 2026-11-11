"""Apply source-page corrections to the pending independent set; never run RAG."""
import copy
import csv
import hashlib
import json
import difflib
from pathlib import Path

from contract_v1 import make_rag_input, validate_rag_input, validate_test_case

ROOT = Path(__file__).parent
SOURCE = ROOT / 'datasets/independent_120_v2_behavior_pending_review.jsonl'
DEST = ROOT / 'datasets/independent_120_v2_source_revised_pending_review.jsonl'
DELTA = ROOT / 'reviews/independent_120_v2_source_revisions.json'
COVERAGE = ROOT / 'reviews/independent_120_v2_58_review_coverage.csv'
HUMAN = ROOT / 'reviews/independent_120_v2_58_final_human_diff.csv'
ORIGINAL_DIFF = ROOT / 'reviews/independent_120_v2_final_pending_diff.csv'

# Page numbers are 1-based PDF pages, not printed page numbers. Inspect rendered
# local source PDFs before changing this map. Every table question T001-T015,
# and all nine table-based clarification cases, were inspected on these pages.
VERIFIED_TABLE_PAGES = {
 'T001':[51], 'T002':[69], 'T003':[173], 'T004':[207], 'T005':[216],
 'T006':[14], 'T007':[14,15], 'T008':[15], 'T009':[16,17], 'T010':[17],
 'T011':[73], 'T012':[113], 'T013':[128], 'T014':[260], 'T015':[293],
 'Q011':[216], 'Q012':[35], 'Q013':[163], 'Q014':[268], 'Q015':[211],
 'Q016':[16], 'Q017':[51], 'Q018':[99,100], 'Q019':[168,169]
}
VISUALLY_CHECKED_PAGES = {
 'cn.beijing.db11t995': {51,55,69,72,106,127,128,173,207,216},
 'cn.gb55033': {14,15,16,17,18,23,24,25,28,31},
 'cn.gb50157': {35,73,99,100,113,128,159,161,163,168,169,211,249,260,268,293},
}
SOURCE_PDFS = {
 'cn.beijing.db11t995': ROOT.parent / 'data/raw/城市轨道交通工程设计标准.pdf',
 'cn.gb55033': ROOT.parent / 'data/raw/GB55033-2022_城市轨道交通工程项目规范.pdf',
 'cn.gb50157': ROOT.parent / 'data/raw/GB50157-2013_地铁设计规范.pdf'
}
SEEN_SAME_PAGE_FACT_COMPARISON = {
 'THARD-002':'已见题仅问基床表层K30、K、Evd及R7压实指标；本题问横坡、厚度或缺项目测量，两者非同一事实。',
 'FINAL-CAND-HARD-003':'已见题问直流牵引系统1500V电压波动范围；本题问外部电源功率因数或缺项目峰值，非同一事实。',
 'IND-012':'已见题问无砟轨道扣件材料和性能；本题问道床结构高度或轨枕数量，非同一事实。',
 'FINAL-CAND-ORD-003':'已见题问集中式/分散式中压网络电压等级；本题问牵引用电负荷类别和项目配置，非同一事实。',
}
EXPECT_HASH = {
 'cn.beijing.db11t995': 'e5ca2388ad68ed7b21b6092e66c12a73c74c17de8b532bef91c5b2ea57be78f7',
 'cn.gb55033': '907ffd92c569f79f163121904cccce69bc20905f9563854960bd184ca76f6fef',
 'cn.gb50157': 'a1130f89afba11f00fdb3353375aa1c424b4eb44d462ee6bd1de2835c235dab3'
}


def hash_file(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(case, fact_id):
    return case['evidence_groups'][[g['fact_id'] for g in case['evidence_groups']].index(fact_id)]['alternatives'][0]['all_of'][0]


def drop_fact(case, fact_id):
    case['necessary_facts'] = [f for f in case['necessary_facts'] if f['fact_id'] != fact_id]
    case['evidence_groups'] = [g for g in case['evidence_groups'] if g['fact_id'] != fact_id]
    assert all(fact_id not in row['fact_ids'] for row in case['numeric_constraints_v2'])


def fix(case):
    ident = case['case_id']
    if ident == 'I120-T002':
        case['question'] = case['question'].replace('换乘路径沿路设施瓶颈处', '换乘路径端部设施（站台、楼扶梯）瓶颈处')
        case['reference_answer'] = case['reference_answer'].replace('换乘路径沿路设施', '换乘路径端部设施')
        case['necessary_facts'][3]['description'] = '评价范围为换乘路径端部设施（站台、楼扶梯）'
        quote = '瓶颈设施最大等待人数（人）；评价范围：换乘路径端部设施（站台、楼扶梯）；<50：良好；50～200：一般；>200：差。'
        for group in case['evidence_groups']: group['alternatives'][0]['all_of'][0]['quote'] = quote
    elif ident == 'I120-N015':
        case['question'] = case['question'].replace('现浇和装配式钢筋混凝土结构氯离子扩散系数', '防水混凝土与装配式钢筋混凝土结构的氯离子扩散系数')
    elif ident == 'I120-T007':
        premise = {'evidence_id':'T007-P14-CLAUSE','document_id':'cn.gb55033',
          'document_version':'2022','page':14,'article':'3.0.5',
          'quote':'当车辆存在低于运行面以下部分且无安装设备时，建筑限界下部距设备限界的轨道最小安全间隙应符合表3.0.5-2的规定。'}
        for group in case['evidence_groups']:
            group['alternatives'][0]['all_of'].insert(0, copy.deepcopy(premise))
        case['source_excerpt_visual_transcription'] = 'PDF第14页3.0.5下部条件；第15页表3.0.5-2跨座式单轨、中低速磁浮、AGT均为100mm，地铁列为—。'
    elif ident == 'I120-T009':
        # 3.0.8 really supports F3, but it was not asked. Make it a cited
        # context condition instead of a mandatory generated answer.
        drop_fact(case,'F3')
        case['reference_answer'] = case['reference_answer'].replace('；任何工况下站台面不应高于客室地板面', '')
        ref(case,'F1')['quote'] = '表3.0.8：地铁／空车静止／车站站台面与车辆客室地板面间的高差≤50mm。'
        ref(case,'F2')['quote'] = '续表3.0.8：中低速磁浮／悬浮静止／车站站台面与车辆客室地板面间的高差≤30mm。'
        case['source_excerpt_visual_transcription'] = 'PDF第16页3.0.8正文另规定任何工况下站台面不应高于地板面；本题只问第16-17页的两行高差上限。'
    elif ident == 'I120-T011':
        drop_fact(case,'F3')
        case['reference_answer'] = case['reference_answer'].replace('；单线加宽在曲线外侧，双线在外股曲线外侧','')
    elif ident == 'I120-T015':
        drop_fact(case,'F3')
        case['reference_answer'] = case['reference_answer'].replace('；无法满足标准要求时应采取降噪措施','')
    elif ident == 'I120-Q014':
        case['clarification_annotation_v2']['required_fields'] = [
         '车库种类：停车库、列检库、月检库、临修库、架修库、油漆库或调机车库',
         '仅当停车库或列检库的括号值与非括号值都可能适用时：车辆为接触轨供电还是架空接触网供电；其他车库不强制追问此项'
        ]
        case['reason_for_refusal_or_clarification'] = '表27.3.14按车库种类列值；停车库、列检库的括号数值按表注5供接触轨供电车辆使用，非括号数值供架空接触网车辆使用。'
    elif ident == 'I120-Q019':
        case['clarification_annotation_v2']['required_fields'] = [
         '电缆种类：电力电缆或控制电缆',
         '敷设地点：电缆通道或电缆沟',
         '所问支架间距的方向：水平或垂直（电缆沟垂直列为—时不得给出本表数值）'
        ]
        case['reason_for_refusal_or_clarification'] = '续表15.4.3的“电缆支架之间的距离”按电力/控制电缆和通道/电缆沟、水平/垂直四列列值；电缆沟垂直列为—。'
    elif ident == 'I120-T003':
        # Found while visually checking all 15 tables: source explicitly says
        # H>10m, leaving exactly 10m unassigned. Never fill that gap by inference.
        case['question'] = case['question'].replace('不小于10m','大于10m')
        case['reference_answer'] = case['reference_answer'].replace('H≥10m','H>10m')
        case['necessary_facts'][1]['description'] = case['necessary_facts'][1]['description'].replace('H≥10m','H>10m')
        case['numeric_constraints'][1]['condition'] = case['numeric_constraints'][1]['condition'].replace('H≥10m','H>10m')
        case['numeric_constraints_v2'][1]['conditions'] = [s.replace('H≥10m','H>10m') for s in case['numeric_constraints_v2'][1]['conditions']]
        for group in case['evidence_groups']:
            group['alternatives'][0]['all_of'][0]['quote'] = '表19.2.13：H<10m，上导轨转弯半径≥2600mm；H>10m，上导轨转弯半径≥3600mm；表未列H=10m。'
        case['source_excerpt_visual_transcription'] = '表19.2.13（PDF第173页）上导轨转弯半径：H<10m为≥2600mm，H>10m为≥3600mm；H=10m无该表行。'
    else:
        return False
    return True


def main():
    for spec,pdf in SOURCE_PDFS.items():
        assert hash_file(pdf) == EXPECT_HASH[spec], spec
    before = [json.loads(s) for s in SOURCE.read_text(encoding='utf-8').splitlines()]
    after = copy.deepcopy(before)
    delta=[]
    for old,case in zip(before,after):
        if not fix(case):continue
        changed={key:{'before':old.get(key),'after':case.get(key)} for key in case if old.get(key)!=case.get(key)}
        ident=case['case_id']; pdf=SOURCE_PDFS[case['query_scope']['spec_ids'][0]]
        pages=VERIFIED_TABLE_PAGES.get(ident[-4:], [128] if ident=='I120-N015' else [])
        # N015 and all corrected T/Q entries are source page verified.
        assert pages,ident
        delta.append({'case_id':ident,'source_pdf':pdf.name,'source_sha256':hash_file(pdf),
          'pdf_pages_1_based':pages,'basis':'rendered original PDF; article/table and relevant note visually checked',
          'changed_fields':changed,'reviewer_type':'ai','human_approved':False})
    assert len(delta)==9 and len(after)==120
    for case in after:
        validate_test_case(case)
        validate_rag_input(make_rag_input(case))
        assert case['schema_version']=='rag-eval.test-case.v2'
    DEST.write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in after),encoding='utf-8')
    audit=json.loads((ROOT/'reviews/independent_120_v2_ai_change_review.json').read_text(encoding='utf-8'))
    original=list(csv.DictReader(ORIGINAL_DIFF.open(encoding='utf-8-sig',newline='')))
    seen=json.loads((ROOT/'datasets/independent_120_seen_inventory.json').read_text(encoding='utf-8'))['records']
    old_by={c['case_id']:c for c in before}; by_id={c['case_id']:c for c in after}
    delta_by={d['case_id']:d for d in delta}
    coverage=[]; human=[]
    for row in original:
        ident=row['case_id'];case=by_id[ident]; old=old_by[ident]
        refs=[r for g in case['evidence_groups'] for a in g['alternatives'] for r in a['all_of']]
        pages=VERIFIED_TABLE_PAGES.get(ident[-4:],[])
        doc=case['query_scope']['spec_ids'][0]
        indicated=sorted(set(pages or [r['page'] for r in refs] or [r['pdf_page'] for r in case.get('supported_source_references',[])] or case.get('ambiguity_source_pages',[])))
        visually_checked=all(p in VISUALLY_CHECKED_PAGES[doc] for p in indicated)
        assert indicated and visually_checked,(ident,indicated)
        earlier=[]
        if old.get('source_review'):
            earlier.append('原始source_review: '+json.dumps(old['source_review'],ensure_ascii=False))
        if ident.startswith('I120-C'):
            earlier.append('早期AI文本逐条核对：independent_120_answer_review_batch1.json；仅原标注且不覆盖v2关联')
        if ident.startswith(('I120-R','I120-Q')):
            earlier.append('早期AI行为草案复核：independent_120_behavior_review_batch1.json；仅原题意/拒答与澄清机制')
        earlier.append('原版用户确认历史保存；该签核不适用于v2评分变化')
        new=['v2评分变更：'+row['change_type']]
        if ident in {d['case_id'] for d in delta}:new.append('本轮修订：见independent_120_v2_source_revisions.json')
        new.append('本轮目视核原PDF页：'+','.join(map(str,indicated)))
        neighbors=sorted(((difflib.SequenceMatcher(None,case['question'],item['question']).ratio(),item['id']) for item in seen),reverse=True)[:3]
        same_page=[item['id'] for item in seen if any(loc.get('document')==SOURCE_PDFS[doc].name and loc.get('page') in indicated for loc in item.get('locations',[]))]
        same_page=list(dict.fromkeys(same_page))
        same_page_decisions=[SEEN_SAME_PAGE_FACT_COMPARISON[i] for i in same_page]
        new.append('历史已见索引定位/题干相似度初筛：同PDF页 '+','.join(same_page[:5])+'；近邻 '+','.join(f'{i}:{score:.2f}' for score,i in neighbors))
        if same_page_decisions:new.append('同PDF页事实差异初审：'+' | '.join(same_page_decisions))
        missing=[]
        if ident=='I120-R012':
            missing.append('13.1.4明确列车站、人行通道防水等级，未单列出入口；核准可选支持前提是否能适用于所问出入口，不能据条文推出具体项目合规')
        if ident=='I120-Q015':
            missing.append('19.1.2未给无集中空调且每层封闭面积≤2000m²时的一级/二级分支；不宜强迫回答该未覆盖分支，需裁定允许的后续行为')
        if ident=='I120-T003':
            missing.append('表19.2.13在H=10m时无行；新题只问H<10m和H>10m，不得外推等于10m')
        if ident.startswith('I120-R'):
            missing.append('逐题人工确认支持前提可选、缺项目事实与禁止断言范围')
        if ident.startswith('I120-Q'):
            missing.append('逐题人工确认必问字段与可接受问法；未来分支仅诊断，不计本轮')
        if ident.startswith(('I120-N','I120-C','I120-T')):
            missing.append('逐题人工确认新增数值约束、条件、关联fact_id与比较方向')
        missing.append('本轮新版语义重叠与历史已见题事实核对尚无独立人工结论')
        missing.append('新版本人工签核尚缺')
        item={'case_id':ident,'expected_action':case['expected_action'],
          'source_document':case['query_scope']['spec_ids'][0],
          'source_pdf_pages_1_based':','.join(map(str,indicated)),
          'original_pdf_page_visual_check':'verified_this_round',
          'source_pdf_sha256':EXPECT_HASH[doc],
          'ai_reviewer':'Codex AI',
          'known_seen_same_pdf_page_ids':','.join(same_page),
          'known_seen_same_page_fact_comparison':' | '.join(same_page_decisions),
          'known_seen_lexical_nearest':','.join(f'{i}:{score:.2f}' for score,i in neighbors),
          'original_review_still_applicable':' | '.join(earlier),
          'new_change_checks':' | '.join(new),
          'still_missing':' | '.join(missing),'human_decision':'','human_reviewer':'','human_reviewed_at':''}
        coverage.append(item)
        human.append({**row,'change_type':row['change_type']+('；本轮PDF原文修订' if ident in {d['case_id'] for d in delta} else ''),
            'scored_now':json.dumps({k:v for k,v in case.items() if k in ('numeric_constraints_v2','refusal_annotation_v2','clarification_annotation_v2')},ensure_ascii=False),
            'diagnostic_only':json.dumps({'ambiguity_source_pages':case.get('ambiguity_source_pages',[]),'supported_source_references':case.get('supported_source_references',[])},ensure_ascii=False),
            'question_current':case['question'],'pdf_pages_1_based':','.join(map(str,indicated)),
            'revision_before_after':json.dumps(delta_by[ident]['changed_fields'],ensure_ascii=False) if ident in delta_by else '',
            'remaining_check':item['still_missing'],
            'new_review_status':'pending_human_review','human_decision':'','reviewer':'','reviewed_at':'','review_notes':''})
    for path,items in ((COVERAGE,coverage),(HUMAN,human)):
        with path.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(items[0]));writer.writeheader();writer.writerows(items)
    DELTA.write_text(json.dumps({'input_sha256':hash_file(SOURCE),'output_sha256':hash_file(DEST),
     'source_pdf_hashes':EXPECT_HASH,'protocol':'rag-eval.test-case.v2','public_input':'rag-eval.rag-input.v1',
     'corrections':delta,'corrected_case_ids':[d['case_id'] for d in delta],
     'additional_discovery':'T003 PDF p173 has H>10m, not H≥10m; exactly H=10m lacks table assignment',
     'specific_remaining_for_human_adjudication':{
        'I120-R012':'13.1.4对车站及人行通道有规定，但未单独列出入口；核定可选支持前提是否恰当，仍不得据此判定具体项目合规。',
        'I120-Q015':'19.1.2未覆盖无集中空调且每层封闭面积≤2000m²的一级/二级分支；明确允许后续说明标准范围不涵盖该分支。',
        'I120-T003':'原表H<10m与H>10m均有值，等于10m未列出；修订题只问有值的两行，不得外推。'
     },
     'visual_table_coverage':VERIFIED_TABLE_PAGES,'visually_checked_source_pages':{k:sorted(v) for k,v in VISUALLY_CHECKED_PAGES.items()},'cases':120,'review_rows':58,
     'reviewer':'Codex AI','human_approved':False,'formal_run_allowed':False,
     'remaining_checks':'See 58-case coverage CSV; R012 optional source scope, Q015 unprovided branch and T003 exact 10m caveat require human adjudication; all 58 need new human signoff and semantic overlap recheck',
     'rag_invoked':False,'independent_run_started':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'changed':[d['case_id'] for d in delta],'dataset_sha256':hash_file(DEST),'coverage':len(coverage)},ensure_ascii=False))


if __name__=='__main__':main()
