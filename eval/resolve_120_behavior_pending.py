"""Offline, reproducible adjudication of 23 behavior annotations; no RAG access."""
import csv
import hashlib
import json
from pathlib import Path
from contract_v1 import validate_test_case, make_rag_input, validate_rag_input

ROOT = Path(__file__).parent
SOURCE = ROOT / 'datasets/independent_120_v2_pending_review.jsonl'
TARGET = ROOT / 'datasets/independent_120_v2_behavior_pending_review.jsonl'
REPORT = ROOT / 'reviews/independent_120_v2_behavior_decisions.json'
SHEET = ROOT / 'reviews/independent_120_v2_final_pending_diff.csv'

# Each entry identifies independently checkable project data, rather than claiming a
# standard can establish an unknown project's measured or installed condition.
MISSING = {
 7: ('该项目高峰小时牵引负荷计算所需线路、车辆与运营参数及计算结果', '该项目牵引负荷峰值为某个 MW 数值'),
 8: ('该路基设计洪水位、积水位、冻胀条件、设计高程及采用的高程基准', '该路肩最终设计高程为某个米数'),
 9: ('该线路轨道形式、适用过渡段和实测工后沉降及沉降速率', '该线路路桥过渡段已经合格'),
 10: ('该配电装置长度与柜后通道布置、出口实况', '现有一个出口符合规范'),
 11: ('该项目车辆类型、运行条件及屏蔽门至车体设计或实测间隙', '该项目现状间隙合格'),
 12: ('该站出入口结构、防水设计与相关现场或验收资料', '该站出入口防水设计已满足规范'),
 13: ('甲线路轨道类型、对应路桥过渡段实测沉降与沉降速率', '甲线路工后沉降合格'),
 14: ('乙线车挡设备耐撞参数与验收资料', '乙线现用车挡合格'),
 15: ('丙站光缆绝缘测试和施工验收记录', '丙站光缆已通过验收'),
 16: ('丁区间水文与冻胀资料、设计和实测路肩高程', '丁区间既有路肩高程合格'),
 17: ('戊站实际接驳设施布局图及对应验收资料', '戊站接驳布局符合要求'),
 18: ('己站机坑排水、油水分离设施的竣工与性能资料', '己站排水及油水分离设施合格'),
 19: ('庚线路最终供电设计文件或实际供电方案', '庚线路最终采用混合式供电'),
 20: ('辛线路实际负荷设计及供电配置、验收资料', '辛线路供电配置已经合规'),
}
FIELDS = {
 11: ['车站所在区域', '车站类型'],
 12: ['车辆类型（A 型或 B 型）', '车体是否设司机室及司机室配置'],
 13: ['屏正面还是屏背面至墙', '若为屏正面：是否有人值守'],
 14: ['车库种类（停车库、列检库、月检库等）', '适用的表注或括号标示条件'],
 15: ['是否采用集中空调', '每层封闭建筑面积及相应分级适用条件'],
 16: ['车辆制式', '速度等级', '若为地铁：车门形式'],
 17: ['道床形式', '正线还是配线', '曲线半径或坡度所属条件'],
 18: ['所处环境类别及适用表', '混凝土强度等级等材料条件'],
 19: ['电缆类型（电力或控制）', '通道或电缆沟布置', '水平还是垂直间距及所指支架位置'],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases = [json.loads(line) for line in SOURCE.read_text(encoding='utf-8').splitlines()]
    decisions = []
    for case in cases:
        ident = case['case_id']
        num = int(ident[-3:])
        if ident.startswith('I120-R') and num in MISSING:
            missing, forbidden = MISSING[num]
            old = case['refusal_annotation_v2']
            source = case['supported_source_references']
            assert source and all(x.get('source_excerpt') and x.get('article') for x in source), ident
            # The prompt asks for an unsupported project conclusion. Stating the
            # standard's premise is permitted, but not necessary to refuse correctly.
            old['supported_facts'][0]['description'] = '可选说明的规范前提：' + source[0]['source_excerpt'].strip()
            old['missing_facts'] = [{'fact_id': 'M1', 'description': missing}]
            old['allowed_explanation'] = [
                '必须说明缺少项目资料，不能据规范前提判定该项目的具体结果。',
                '可选说明对应规范前提，但不得把规范要求当成项目实际情况。',
                '禁止无依据断言：' + forbidden,
            ]
            decisions.append({'case_id': ident, 'original_reason': case['reason_for_refusal_or_clarification'],
                'source_references': source, 'scored_now': {'missing_facts': old['missing_facts'],
                    'allowed_explanation': old['allowed_explanation'], 'supported_premise_required': False},
                'diagnostic_only': {'supported_source_references': source},
                'change': '具体化缺失事实及禁止断言；支持前提仅可选说明；待人工审核'})
        elif ident.startswith('I120-Q') and num in FIELDS:
            old = case['clarification_annotation_v2']
            old['required_fields'] = FIELDS[num]
            assert old['branches'] == [], ident
            decisions.append({'case_id': ident, 'original_reason': case['reason_for_refusal_or_clarification'],
                'scored_now': {'required_fields': FIELDS[num],
                    'acceptable_clarification': '可合并提问或分开提问；须问清决定适用行列/条件的字段，不能直接指定单一数值。'},
                'diagnostic_only': {'ambiguity_source_pages': case['ambiguity_source_pages'],
                    'future_branches': [], 'branch_evidence_complete': False},
                'change': '澄清字段具体化；分支证据仅诊断且尚不完整；待人工审核'})
        validate_test_case(case)
        validate_rag_input(make_rag_input(case))
    assert len(cases) == 120 and len(decisions) == 23
    assert all(not c['annotation_review'].get('human_approved') for c in cases if c['case_id'] in {d['case_id'] for d in decisions})
    TARGET.write_text(''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in cases), encoding='utf-8')
    previous = json.loads((ROOT / 'reviews/independent_120_v2_migration.json').read_text(encoding='utf-8'))
    renewed = previous['renewed_human_review_required_case_ids']
    assert len(renewed) == 58
    with SHEET.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['case_id','change_type','scored_now','diagnostic_only','old_signature','new_review_status','human_decision','reviewer','reviewed_at','review_notes'])
        writer.writeheader()
        for c in cases:
            if c['case_id'] not in renewed: continue
            d = next((v for v in decisions if v['case_id'] == c['case_id']), None)
            writer.writerow({'case_id': c['case_id'], 'change_type': d['change'] if d else 'v2迁移评分含义变化；见迁移报告',
                'scored_now': json.dumps(d['scored_now'],ensure_ascii=False) if d else '见v2迁移题集及迁移报告',
                'diagnostic_only': json.dumps(d['diagnostic_only'],ensure_ascii=False) if d else '',
                'old_signature': '原题集历史保留；不继承', 'new_review_status': 'pending_human_review',
                'human_decision': '', 'reviewer': '', 'reviewed_at': '', 'review_notes': ''})
    report = {'schema_version': 'rag-eval.test-case.v2', 'public_input_version': 'rag-eval.rag-input.v1',
        'source_sha256': sha(SOURCE), 'output_sha256': sha(TARGET), 'cases': len(cases),
        'resolved_23_case_ids': [d['case_id'] for d in decisions], 'renewed_human_review_required_case_ids': renewed,
        'additional_human_review_required_case_ids': [], 'remaining_behavior_adjudication_case_ids': [],
        'interface_gap_for_this_round': None, 'decisions': decisions,
        'validation': '120 schema, fact/evidence ID links and public input validation passed; 23 behavior annotations checked',
        'rag_invoked': False, 'independent_run_started': False}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('cases','output_sha256','resolved_23_case_ids','additional_human_review_required_case_ids','interface_gap_for_this_round')},ensure_ascii=False))


if __name__ == '__main__': main()
