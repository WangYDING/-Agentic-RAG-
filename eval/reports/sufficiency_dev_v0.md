# Evidence Sufficiency Evaluation

- Cases: 19
- Accuracy: 1.0000
- Precision: 1.0000
- Recall: 1.0000
- F1: 1.0000
- False Accept Rate: 0.0000
- False Refusal Rate: 0.0000
- Confusion Matrix: `{"tp": 8, "fp": 0, "tn": 11, "fn": 0}`

## By Case Type

| type | count | accuracy | FAR | FRR |
|---|---:|---:|---:|---:|
| external_project_info | 2 | 1.0000 | 0.0000 | 0.0000 |
| future_or_current | 2 | 1.0000 | 0.0000 | 0.0000 |
| missing_fact | 2 | 1.0000 | 0.0000 | 0.0000 |
| multi_evidence | 4 | 1.0000 | 0.0000 | 0.0000 |
| ordinary_sufficient | 6 | 1.0000 | 0.0000 | 0.0000 |
| partial_support | 3 | 1.0000 | 0.0000 | 0.0000 |

## Cases

- PASS `SEM-001` (ordinary_sufficient): expected=sufficient, predicted=sufficient; E2明确规定了南北向、东西向和环形线路的上行/下行方向，E1补充了斜向、L型、U型线路的确定原则，两者结合可完整回答线路在不同方向上如何划分上行和下行。
- PASS `SEM-003` (ordinary_sufficient): expected=sufficient, predicted=sufficient; E1明确列出了四类需根据客流动态仿真模拟评价结果修正通行设施及通行空间规模的复杂换乘车站，完整回答了问题。
- PASS `NUM-001` (ordinary_sufficient): expected=sufficient, predicted=sufficient; E1直接规定了列车起动加速度和制动减速度的上限要求，即不宜大于常用加、减速度的90%，且计算起、制动加速度不宜大于0.9m/s2，足以完整回答问题。
- PASS `TAB-002` (ordinary_sufficient): expected=sufficient, predicted=sufficient; 证据E1和E2均明确列出体育场的最小间距为100米，可直接回答问题。
- PASS `TERM-001` (ordinary_sufficient): expected=sufficient, predicted=sufficient; E1直接定义了客流控制期为初期、近期、远期中对系统设计规模要求最高的设计年限，E2进一步说明以客流需求最大者确定，足以完整回答问题。
- PASS `HARD-002` (ordinary_sufficient): expected=sufficient, predicted=sufficient; 证据E1明确规定了马蹄形隧道在距轨顶面3600mm高度处，侧墙有设备或管线时最小间隙不宜小于300mm，无设备或管线时不宜小于200mm，困难地段不得小于100mm，直接完整回答了问题。
- PASS `MULTI-001` (multi_evidence): expected=sufficient, predicted=sufficient; E1规定普线为设计最高运行速度小于或等于100km/h，E2规定快线为大于100km/h，因此恰好100km/h属于普线，问题可完整回答。
- PASS `MHARD-001` (multi_evidence): expected=sufficient, predicted=sufficient; E2明确给出最高运行速度大于100km/h时最大超高150mm、未被平衡超高允许值不大于61mm，适用于120km/h；E1明确地下线整体道床曲线超高宜按半超高设置。三者均有证据支持。
- PASS `MULTI-002` (multi_evidence): expected=insufficient, predicted=insufficient; 证据E1仅提供了纵向坡度的要求，未涉及平面曲线设置要求；其他证据也未包含相关平面曲线规定，故证据不足。
- PASS `MULTI-003` (multi_evidence): expected=insufficient, predicted=insufficient; 证据E1、E2仅说明了全自动运行线路可将正线停车线计入设计停车列位的条件和相关功能，但未定义“什么情况才算全自动运行”，缺少对全自动运行判定标准的证据，因此不足以完整回答用户问题。
- PASS `UA-CAND-A01` (missing_fact): expected=insufficient, predicted=insufficient; 证据仅说明减振级别划分，未提供任何级别对应的具体分贝数值，无法回答所问的最低减振效果。
- PASS `UA-CAND-A02` (missing_fact): expected=insufficient, predicted=insufficient; 证据仅提及三线换乘站需进行客流动态仿真，但未规定具体仿真软件，也未涉及模型校准误差允许值，无法完整回答问题。
- PASS `UA-CAND-B01` (external_project_info): expected=insufficient, predicted=insufficient; 证据未提供国贸站现有岛式站台的实际宽度，无法进行对比；E3虽提供站台宽度标准，但表格数据不完整，不足以确定规范要求的具体宽度值。
- PASS `UA-CAND-B03` (external_project_info): expected=insufficient, predicted=insufficient; 证据仅提供减振措施的一般规定和减振级别划分，未涉及大兴机场线的具体减振产品及现场测试数据。
- PASS `UA-CAND-C01` (future_or_current): expected=insufficient, predicted=insufficient; 证据仅提及北京轨道交通总体情况和全自动运行技术，未给出具体全自动运行线路名称及里程合计，无法完整回答问题。
- PASS `UA-CAND-C03` (future_or_current): expected=insufficient, predicted=insufficient; 提供的证据仅涉及设计标准中的技术说明，未包含任何具体线路的实际发车间隔或通过能力利用率数据，无法回答用户问题。
- PASS `UA-CAND-D01` (partial_support): expected=insufficient, predicted=insufficient; 证据仅说明了非载客联络线在困难条件下的最大坡度为40‰，但未提供采用该困难坡度比普通坡度每公里节省的建设费用信息。
- PASS `UA-CAND-D02` (partial_support): expected=insufficient, predicted=insufficient; E1提供了A型车站台设在曲线上时最小曲线半径不应小于1500m的规定，但证据中未包含西直门站现有站台曲线半径的任何信息，无法判断其是否满足要求。
- PASS `UA-CAND-D03` (partial_support): expected=insufficient, predicted=insufficient; 证据明确了防内涝设计重现期不应低于100年，但未提供北京西站地铁站防淹设施的任何信息，无法判断其能否抵御对应暴雨。