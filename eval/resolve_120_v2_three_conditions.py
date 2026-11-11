"""Resolve three source-boundary issues; no retrieval or evaluation run."""
import copy
import csv
import hashlib
import json
from pathlib import Path

from contract_v1 import make_rag_input, validate_rag_input, validate_test_case
from revise_120_v2_source_issues import EXPECT_HASH, SOURCE_PDFS

ROOT = Path(__file__).parent
OLD = ROOT / 'datasets/independent_120_v2_source_revised_pending_review.jsonl'
NEW = ROOT / 'datasets/independent_120_v2_conditions_pending_review.jsonl'
AUDIT = ROOT / 'reviews/independent_120_v2_three_conditions_resolution.json'
OLD_COVER = ROOT / 'reviews/independent_120_v2_58_review_coverage.csv'
NEW_COVER = ROOT / 'reviews/independent_120_v2_58_conditions_review_coverage.csv'
OLD_HUMAN = ROOT / 'reviews/independent_120_v2_58_final_human_diff.csv'
NEW_HUMAN = ROOT / 'reviews/independent_120_v2_58_conditions_final_human_diff.csv'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)

def update_csv(source, target, changes):
    with source.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        names, rows = reader.fieldnames, list(reader)
    assert len(rows) == 58 and len({r['case_id'] for r in rows}) == 58
    for row in rows:
        if row['case_id'] in changes:
            row.update(changes[row['case_id']])
        assert not any(row.get(k) for k in ('human_decision', 'human_reviewer', 'human_reviewed_at'))
    with target.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)

def main():
    for doc, source in SOURCE_PDFS.items():
        assert digest(source) == EXPECT_HASH[doc], doc
    before = [json.loads(s) for s in OLD.read_text(encoding='utf-8').splitlines() if s.strip()]
    assert len(before) == 120 and len({r['case_id'] for r in before}) == 120
    after = copy.deepcopy(before)
    cases = {r['case_id']: r for r in after}
    r = cases['I120-R012']
    r['supported_source_references'][0]['source_excerpt'] = '13.1.4第2项：车站、人行通道和机电设备集中区段的防水等级应为一级。'
    r['reason_for_refusal_or_clarification'] = ('13.1.4第2项列车站、人行通道及机电设备集中区段，未单列“出入口”；'
        '现有题干也没有该站出入口结构与防水设计等工程资料，无法判断其防水设计是否符合规范。'
        '10.5.7、30.8.3针对出入口防淹或排水，不等同于证明该项目整体防水设计合格。')
    r['refusal_annotation_v2']['supported_facts'][0]['description'] = (
        '可选的规范前提：DB11/T 995-2025第13.1.4条第2项规定车站、人行通道和机电设备集中区段防水等级为一级；原文未单列出入口。'
        '仅在答复提及时核对其原文范围，不要求必须复述。')
    r['refusal_annotation_v2']['missing_facts'][0]['description'] = (
        '该站出入口的具体结构与适用部位、建筑和设备图纸、防水设计及用于判断是否满足规范的相关工程资料')
    r['refusal_annotation_v2']['allowed_explanation'] = [
        '应说明缺少该站出入口的具体工程和防水设计资料，无法判定其是否符合规范；可合理拒绝作出合格结论。',
        '可选说明13.1.4所列车站、人行通道及机电设备集中区段的等级；不得据此断言所有出入口被该条明确单列或已满足规范。',
        '禁止无依据断言：该站出入口防水设计已满足规范，或所有出入口在13.1.4中明确规定为一级；不得把10.5.7、30.8.3的防淹要求当作该工程防水设计合格的证明。',
    ]

    q = cases['I120-Q015']
    q['reason_for_refusal_or_clarification'] = (
        'GB 50157-2013第19.1.2条：地面或高架车站采用集中空调，或每层封闭建筑面积>2000m²且≤3000m²时为二级；'
        '面积>3000m²时为一级。题干未给集中空调和各层封闭建筑面积，本轮应先澄清，不指定项目等级。'
        '若补充后确认未用集中空调且各层面积均≤2000m²，所引条文没有该分支的等级，应明确无法由该条判定，不能补造等级。'
        '后续分支仅作诊断，不要求本轮评分时完成分支证据链。')
    q['clarification_annotation_v2']['required_fields'] = [
        '该地面或高架车站是否采用集中空调',
        '每层封闭建筑面积分别是多少平方米，是否存在超过2000m²或超过3000m²的楼层',
    ]
    assert q['clarification_annotation_v2']['branches'] == []

    t = cases['I120-T003']
    assert t == next(x for x in before if x['case_id'] == t['case_id'])
    assert 'H<10m' in t['reference_answer'] and 'H>10m' in t['reference_answer']
    assert [c['conditions'][0] for c in t['numeric_constraints_v2']] == ['提升高度H<10m，上导轨', 'H>10m，上导轨']
    for part in (t['question'], t['reference_answer'], dump(t['necessary_facts']), dump(t['numeric_constraints']), dump(t['numeric_constraints_v2']), dump(t['evidence_groups'])):
        assert 'H≥10' not in part and 'H>=10' not in part
    assert 'H=10m无该表行' in t['source_excerpt_visual_transcription']

    old_map = {x['case_id']: x for x in before}
    for case in after:
        assert case == old_map[case['case_id']] or case['case_id'] in ('I120-R012', 'I120-Q015')
        validate_test_case(case)
        validate_rag_input(make_rag_input(case))
    assert {a: sum(c['expected_action'] == a for c in after) for a in ('answer', 'clarify', 'refuse')} == {'answer':90,'clarify':10,'refuse':20}
    NEW.write_text(''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in after), encoding='utf-8')

    evidence = {
        'I120-R012': {'pages': {'cn.beijing.db11t995':[66,106,112,236]}, 'result':
            '13.1.4第2项未单列出入口；10.5.7和30.8.3涉及出入口防淹/排水；13.7.12为顶管法隧道的条件性防水规定，均不证明所有出入口防水等级或具体工程合格。',
            'scoring': 'refuse；须指出缺少工程事实；13.1.4的准确范围为可选说明。'},
        'I120-Q015': {'pages': {'cn.gb50157':[211]}, 'result':
            '19.1.2有>3000m²一级、集中空调或>2000m²且≤3000m²二级；无集中空调且各层≤2000m²时该条未给等级。',
            'scoring': 'clarify；询问集中空调和各层封闭建筑面积。未来无对应等级分支仅诊断，不能补造。'},
        'I120-T003': {'pages': {'cn.beijing.db11t995':[173]}, 'result':
            '表19.2.13仅列H<10m及H>10m；H=10m无行，不插值外推；现题只问两个严格区间。',
            'scoring': 'answer；本轮题干未问H=10m；当前标注无须修改，若改问等于10m须说明原表不能直接回答。'},
    }
    audit = {'input':str(OLD.relative_to(ROOT)), 'input_sha256':digest(OLD), 'output':str(NEW.relative_to(ROOT)),
             'output_sha256':digest(NEW), 'reviewer':'Codex AI', 'reviewer_type':'ai', 'human_approved':False,
             'pdf_sha256':EXPECT_HASH, 'case_decisions':{}}
    for ident, item in evidence.items():
        pre, post = old_map[ident], cases[ident]
        changed = {k:{'before':pre[k], 'after':post[k]} for k in pre if pre[k] != post[k]}
        audit['case_decisions'][ident] = {**item, 'expected_action':post['expected_action'], 'changed_fields':changed,
                                          'human_review':'pending'}
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')

    cv = {}
    hv = {}
    for ident, item in evidence.items():
        brief = item['result'] + ' 本轮处理：' + item['scoring']
        cv[ident] = {'new_change_checks': '原有记录继续适用；本次新增PDF页面核查：'+dump(item['pages'])+'；'+brief,
                     'still_missing':'新版标注须由人工逐题确认；历史已见题事实语义核查尚无独立人工结论；人工签核尚缺',
                     'original_pdf_page_visual_check':'verified_original_pdf_pages_ai'}
        hv[ident] = {'scored_now': dump({k:cases[ident][k] for k in ('expected_action', 'refusal_annotation_v2' if ident=='I120-R012' else 'clarification_annotation_v2') if k in cases[ident]}) if ident!='I120-T003' else dump({'expected_action':'answer','necessary_facts':cases[ident]['necessary_facts'],'numeric_constraints_v2':cases[ident]['numeric_constraints_v2']}),
                     'diagnostic_only': dump({'future_branch':item['result']}) if ident=='I120-Q015' else dump({'source_boundaries':item['result']}),
                     'revision_before_after': dump(audit['case_decisions'][ident]['changed_fields']) if ident!='I120-T003' else '本次无字段变化；原版本已修正H>10m，核验H=10m无表行',
                     'remaining_check':'人工确认本次事实边界和本轮评分；不得代填人工签核',
                     'pdf_pages_1_based':','.join(str(n) for pages in item['pages'].values() for n in pages)}
    update_csv(OLD_COVER, NEW_COVER, cv)
    update_csv(OLD_HUMAN, NEW_HUMAN, hv)
    print(dump({'output':str(NEW),'sha256':digest(NEW),'review':str(AUDIT), 'coverage':str(NEW_COVER),'human_diff':str(NEW_HUMAN)}))

if __name__ == '__main__':
    main()
