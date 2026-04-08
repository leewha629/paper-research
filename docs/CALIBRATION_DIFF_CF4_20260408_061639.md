# Phase D v2 — Calibration Diff (CF4)

실행: 2026-04-08T06:20:44.986681Z  (COMMIT)
collection: **CF4**
총 50건 (성공 50, 실패 0)
백업: /Users/igeonho/paper-research/data/backups/papers_pre_recalibrate_20260408_061639.db

변화량 큰 순으로 정렬. before_score는 기존 `papers.relevance_score`, before_folder는 매핑된 시스템 폴더, after_*는 RELEVANCE_SYSTEM v2 평가 결과.

| 제목 | 이전 점수 | 이전 폴더 | 신규 점수 | 신규 폴더 | Δ | matched_tokens | reason |
|---|---|---|---|---|---|---|---|
| Unveiling the Function of Oxygen Vacancy on Facet-Dependent CeO2 for the Catalyt | 9 | 풀분석 추천 | 3 | 휴지통 | -6 | CeO2, catalytic destruction, monochloromethane | 주 연구 분야인 CF₄ 대신 모노클로로메탄(MCM)을 다루고 있으며, 촉매 메커니즘은 Lewis acid 기반의 C-Cl 활성화에 초점을 맞추고 있어 직접적인 관련성이 낮습니다. |
| Design, characterization and evaluation of Ce-modified cobalt catalysts supporte | 7 | 풀분석 추천 | 1 | 휴지통 | -6 | methane oxidation, Co3O4, alpha alumina | 주 연구 분야인 CF₄ 분해와 무관하며, 반응물(CH₄)과 촉매의 역할이 완전히 다름. |
| Enhanced activity and stability of MgO-promoted Ni/Al2O3 catalyst for dry reform | 7 | 풀분석 추천 | 1 | 휴지통 | -6 | Al2O3, shared support only | 주 연구 분야인 CF₄ 분해와 무관한 메탄 건류합성(DMR) 연구이며, 촉매 지지체(Al2O3)만 공유함. |
| Boosted 1,3-dichlorobenzene catalytic destruction over P-Co-LaCoO3 by rational e | 7 | 풀분석 추천 | 2 | 휴지통 | -5 | CF4 (title only), P-Co-LaCoO3 | 제목은 CF₄ 촉매 분해를 다루지만, 실제 논문 주제는 1,3-dichlorobenzene(Cl-VOC) 처리이며, 촉매 조성도 사용자의 주 연구 시스템(Al/Zr/Ga/W/Ce)과 무관합니다. |
| Characteristics of catalytic destruction of dichloromethane and ethyl acetate mi | 8 | 풀분석 추천 | 3 | 휴지통 | -5 | dichloromethane, ethyl acetate, VOCs | 주요 반응물이 DCM과 에틸 아세테이트(VOCs)이며, CF₄ 분해나 Lewis acid 기반 가수분해 메커니즘과 거리가 멀다. |
| Study on the effects and mechanism of temperature on the thermal decomposition c | 8 | 풀분석 추천 | 3 | 휴지통 | -5 | C4F7N, thermal decomposition | 주요 반응물은 C4F7N/CO2/O2 혼합가스이며, CF4 직접 언급이 없고, 촉매 대신 열분해(thermal decomposition)에 초점을 맞추었으므로 점수가 낮습니다. |
| High-Efficiency PFC Abatement System Utilizing Plasma Decomposition and Ca(OH)$_ | 8 | 풀분석 추천 | 3 | 휴지통 | -5 | PFC, plasma decomposition (title only) | abstract 부재로 메커니즘 확인 불가. 제목에 CF4는 언급되었으나, 촉매(Lewis acid)의 구체적인 역할이나 가수분해 메커니즘이 확인되지 않아 점수가 낮게 책정됨. |
| Heterobimetallic CoCeO derived from cobalt partially-substituted Ce-UiO-66 for c | 7 | 풀분석 추천 | 3 | 휴지통 | -4 | chlorobenzene, CoCeO, UiO-66 | 제목에 CF₄ 언급이 없고, 처리 대상이 클로로벤젠(Cl-VOC)이며, 촉매 메커니즘이 F-화합물 가수분해와 다르므로 점수가 낮게 책정되었습니다. |
| PFC Abatement Using Microwave plasma source with annular-shaped slot antenna at  | 7 | 풀분석 추천 | 3 | 휴지통 | -4 | PFC, microwave plasma (title only) | abstract 부재로 메커니즘 확인 불가. 제목에 CF4는 언급되었으나, 촉매(catalyst) 관련 토큰이 없어 0층 룰에 따라 최대 5점 중 3점 부여. |
| Thermal Decomposition and Oxidative Decomposition Mechanism of HFC-134a by Exper | 7 | 풀분석 추천 | 3 | 휴지통 | -4 | HFC-134a, thermal decomposition | 반응물(HFC-134a)이 CF₄와 직접 일치하지 않으며, 촉매/가수분해 메커니즘에 대한 언급이 없어 점수가 낮게 책정되었습니다. |
| Thermal stability and decomposition mechanism of HFO‐1336mzz(Z) as an environmen | 7 | 풀분석 추천 | 3 | 휴지통 | -4 | HFO-1336mzz(Z), thermal decomposition, DFT | 주요 반응물인 HFO-1336mzz(Z)는 CF₄와 같은 메커니즘으로 간주되지 않으며, 촉매를 사용하지 않은 열분해 연구이므로 점수가 낮게 책정되었습니다. |
| Study on thermal decomposition characteristics of C6F12O/O2/CO2 gas mixtures | 7 | 풀분석 추천 | 3 | 휴지통 | -4 | C6F12O, thermal decomposition | C6F12O의 열분해 특성 연구로, CF₄ 촉매 분해/가수분해 메커니즘이 아니며 촉매가 언급되지 않았습니다. |
| Influence of Oxygen on the Thermal Decomposition Properties of C4F7N–N2–O2 as an | 7 | 풀분석 추천 | 3 | 휴지통 | -4 | C4F7N, thermal decomposition | 주요 반응물은 C4F7N이며, CF₄ 직접 분해나 Lewis acid 기반 촉매 가수분해에 대한 내용이 아니므로 점수가 낮게 책정되었습니다. |
| Innovative Surface Wave Plasma Reactor Technique for PFC Abatement | 7 | 풀분석 추천 | 3 | 휴지통 | -4 | PFC, surface wave plasma (title only) | abstract 부재로 메커니즘 확인 불가. 제목에 CF4와 catalyst 토큰이 모두 명시되지 않았고, surface wave plasma는 촉매 역할이 명확하지 않아 0층 룰에 따라 최대 3점 부여. |
| Catalytic destruction of oxalate in the supernatant stream generated during plut | 4 | 검토 대기 | 1 | 휴지통 | -3 | oxalate, catalytic destruction | 주 연구 분야인 CF₄ 분해와 무관한 옥살산염(oxalate) 분해 연구이며, 촉매 조성도 관련성이 낮습니다. |
| Alumina-Supported Silver Catalyst for O_3-Assisted Catalytic Abatement of CO: Ef | 4 | 검토 대기 | 1 | 휴지통 | -3 | Ag/Al2O3, CO oxidation | 제목에 언급된 촉매(Ag/Al2O3)는 CO 산화에 사용되었으며, 주 연구 분야인 CF₄ 분해와 반응물/메커니즘이 완전히 다릅니다. |
| Insight into the decomposition mechanism of C6F12O-CO2 gas mixture | 7 | 풀분석 추천 | 4 | 검토 대기 | -3 | C6F12O, thermal decomposition | 주요 반응물은 C6F12O이며, CF₄ 직접 분해 연구가 아니며, 촉매 메커니즘 대신 열분해(thermal decomposition) 및 분자 동역학(ReaxFF) 계산에 초점을 맞추어 점수가 제한됨. |
| Induced activation of the commercial Cu/ZnO/Al2O3 catalyst for the steam reformi | 4 | 검토 대기 | 1 | 휴지통 | -3 | methanol, steam reforming | 반응물(메탄올)과 촉매의 주된 반응(스팀 개질)이 사용자 연구 분야(CF₄ 가수분해)와 완전히 달라 지지체만 공유함. |
| Stabilizing the isolated Pt sites on PtGa/Al2O3 catalyst via silica coating laye | 4 | 검토 대기 | 1 | 휴지통 | -3 | propane dehydrogenation, PtGa/Al2O3, silica coating | 사용자 주 연구 분야인 CF₄ 분해와 무관한 프로판 탈수소화(PDH) 반응에 대한 논문으로, 지지체만 공유하는 경우에 해당합니다. |
| High-Entropy (Cocrfemnni)3o4 Catalysts for Propane Catalytic Destruction: Effect | 4 | 검토 대기 | 1 | 휴지통 | -3 | none | 제목에 CF₄ 언급이 없고, 촉매가 프로판(Propane) 산화에 사용되어 사용자 연구 분야와 완전히 무관합니다. |
| Effective toluene oxidation under ozone over mesoporous MnOx/γ-Al2O3 catalyst pr | 4 | 검토 대기 | 1 | 휴지통 | -3 | toluene oxidation, shared support only | 반응물(Toluene/Ozone)이 CF₄ 분해와 완전히 다르고, 촉매 지지체만 공유하는 경우이므로 점수가 낮게 책정됨. |
| Promoted adsorption of methyl mercaptan by γ-Al2O3 catalyst loaded with Cu/Mn | 4 | 검토 대기 | 1 | 휴지통 | -3 | gamma-Al2O3, unrelated reaction: mercaptan | 반응물(CH3SH)이 CF4와 완전히 다르며, 촉매 연구지만 반응물 적합성 문제로 점수가 낮게 책정됨. |
| Performances of syngas production and deposited coke regulation during co-gasifi | 4 | 휴지통 | 1 | 휴지통 | -3 | Ni/γ-Al2O3, co-gasification | 연구 주제는 CF₄ 촉매 분해이나, 실제 논문은 바이오매스/플라스틱 가스화 반응에 대한 내용으로, 촉매 지지체만 공유할 뿐 반응물이 완전히 다릅니다. |
| Leveraging Heterogeneous Catalyst Design Principles for Volatile PFAS Destructio | 8 | 풀분석 추천 | 10 | 풀분석 추천 | +2 | CF4, catalytic decomposition, Lewis acidity, catalyst design, Al/Zr/Ga/W/Ce | CF₄ 직접 분해를 목표로 하며, Lewis acid 기반의 다양한 산화물 촉매 설계 원리(Al/Zr/Ga/W/Ce 등)를 다루는 최적의 주제와 내용입니다. |
| H-zeolite supported multi-interface metal catalysts for the catalytic destructio | 7 | 풀분석 추천 | 5 | 자동 발견 | -2 | H-zeolite, catalytic destruction, chlorinated organics | 제목은 제올라이트 기반 할로겐 처리 일반론에 해당하며, CF₄ 직접 언급은 없으나, 촉매-할로겐 활성화 원리 참고 가능하여 5점 부여. |
| Hydrolysis of Tetrafluoromethane (PFC-14) Using Alumina–Zirconia Catalysts Prepa | 8 | 풀분석 추천 | 10 | 풀분석 추천 | +2 | Hydrolysis, Tetrafluoromethane, PFC-14, Alumina-Zirconia, catalysts | CF₄ 직접 분해에 대해 Alumina-Zirconia 조합의 촉매를 사용한 가수분해 메커니즘을 다루고 있어 가장 높은 관련도를 가집니다. |
| The synergistic performance of redox couples enhanced with phase inter-grown cer | 4 | 검토 대기 | 2 | 휴지통 | -2 | three-way catalyst, diesel exhaust | 제목과 주제는 CF₄ 촉매 분해에 초점을 맞추었으나, 실제 논문은 디젤 배기가스(CO/NOx/HC) 산화 촉매에 관한 내용이므로 메커니즘이 완전히 다릅니다. |
| Mechanism of Thermal Decomposition of HFO-1234ze(Z) by DFT Study | 5 | 자동 발견 | 3 | 휴지통 | -2 | HFO-1234ze(Z), DFT study | 주제는 CF₄ 촉매 분해이나, 논문은 HFO-1234ze(Z)의 열분해를 DFT로 다루어 반응물과 메커니즘이 맞지 않음. |
| Decomposition Mechanism of SF6 by Long DC Arc Plasma | 8 | 풀분석 추천 | 6 | 자동 발견 | -2 | CF4, plasma, catalytic | CF₄ 분해를 다루며 촉매 언급은 있으나, 본 연구의 핵심은 장거리 DC 아크 플라즈마를 이용한 분해 메커니즘 규명에 초점이 맞춰져 있어 플라즈마-촉매 시너지로 평가함. |
| Synthesis of the SrO–CaO–Al2O3 trimetallic oxide catalyst for transesterificatio | 3 | 휴지통 | 1 | 휴지통 | -2 | Al2O3, transesterification | 촉매 조성(Al2O3)은 유사하나, 반응물이 바이오디젤 생산을 위한 에스터 교환 반응(transesterification)으로 완전히 달라 메커니즘이 무관합니다. |
| Studies of sulfur poisoning process via ammonium sulfate on MnO2/γ-Al2O3 catalys | 3 | 휴지통 | 1 | 휴지통 | -2 | gamma-Al2O3, unrelated reaction: toluene oxidation | 반응물(톨루엔)이 CF₄와 완전히 다르고, 촉매 연구의 초점이 황 독성(sulfur poisoning)에 맞춰져 있어 관련성이 매우 낮습니다. |
| Hydrolytic decomposition of CF4 over alumina-based binary metal oxide catalysts: | 8 | 풀분석 추천 | 10 | 풀분석 추천 | +2 | CF4, hydrolytic decomposition, alumina-based, gallia-alumina catalyst | CF₄ 직접 분해에 대해 Lewis acid 기반의 Al-Ga 촉매 시스템을 명시하여 가장 높은 관련도를 가집니다. |
| Thermal Decomposition Properties and Mechanism of Hexafluoropropane | 5 | 자동 발견 | 3 | 휴지통 | -2 | C3F6, thermal decomposition (title only) | 제목에 CF₄가 직접 언급되지 않았고, 반응물이 C₃F₆(Hexafluoropropane)이며, abstract가 비어있어 메커니즘 확인이 어렵습니다. |
| The Zr Modified γ-Al2O3 Catalysts for Stable Hydrolytic Decomposition of CF4 at  | 9 | 풀분석 추천 | 10 | 풀분석 추천 | +1 | CF4, hydrolytic decomposition, Zr/γ-Al2O3, Lewis acidity sites | CF₄ 직접 분해에 대해 Lewis acid 기반의 Al-Zr 조합 촉매를 사용하고, 메커니즘(Lewis acidity site)까지 명확히 제시하여 가장 높은 점수를 부여함. |
| The Design of Sulfated Ce/HZSM-5 for Catalytic Decomposition of CF4 | 9 | 풀분석 추천 | 10 | 풀분석 추천 | +1 | CF4, catalytic decomposition, sulfated, Ce/HZSM-5, Lewis acidic sites | CF₄ 직접 분해에 대해 Lewis acid 기반의 HZSM-5/Ce 산화물 촉매를 사용하고, 산성점 증가가 활성점임을 명확히 제시하여 연구 주제와 완벽히 일치함. |
| Synergistic roles of Ru, CeO2, and HZSM-5 in a ternary-active center catalyst fo | 4 | 검토 대기 | 3 | 휴지통 | -1 | dichloromethane, catalytic destruction | 제목에 CF₄ 언급이 없고, 처리 대상이 염소계 유기물(dichloromethane)이며, 촉매 시스템이 제올라이트 기반이므로 CF₄ 메커니즘과 거리가 멂. |
| In-site abatement of CO/NO via regulating bed-media with porous alumina balls du | 2 | 휴지통 | 1 | 휴지통 | -1 | alumina | 반응물(CO/NO)이 CF₄와 완전히 다르고, 촉매 연구의 핵심이 아닌 슬러지 처리 과정에 사용된 지지체만 언급됨. |
| Assessment of the Synergetic Performance of Ceria-Tin-Alumina Mixed Oxides on Di | 2 | 휴지통 | 1 | 휴지통 | -1 | Ce-Sn-Al2O3, diesel exhaust | 제목에 언급된 촉매(Ce-Sn-Al2O3)는 사용자의 주 연구 분야인 CF₄ 분해와 직접적인 관련성이 낮으며, 반응물(Diesel Exhaust)이 완전히 달라 메커니즘이 무관합니다. |
| Heteroatom-Engineered Atomic Electric Fields Activate C-F Bond for Efficient Per | 9 | 풀분석 추천 | 10 | 풀분석 추천 | +1 | CF4, catalytic decomposition, Lewis acidity, Al2O3, Ga-Zn | CF₄ 직접 분해를 목표로 하며, Lewis acid 기반의 Al/Ga 촉매 조합과 C-F 결합 활성화 메커니즘을 상세히 다루고 있습니다. |
| Engineering Calculations for Catalytic Hydrolysis of CF4 | 9 | 풀분석 추천 | 10 | 풀분석 추천 | +1 | CF4, catalytic hydrolysis, Al2O3, Ga-doping, catalytic mechanism | CF₄ 직접 분해 및 가수분해에 대해 Lewis acid 기반의 Al/Ga 촉매 조합을 사용하고, 촉매 메커니즘 및 반응기 설계까지 다루어 가장 높은 관련도를 보입니다. |
| DFAMO/BAMO copolymer as a potential energetic binder: Thermal decomposition stud | 1 | 휴지통 | 2 | 휴지통 | +1 | DFAMO/BAMO | 제목과 초록 모두 CF₄ 또는 촉매 관련 내용이 없어, 지지체만 공유하는 일반적인 열분해 연구로 판단됩니다. |
| Design of a Na-Doped Amorphous Aluminum Catalyst for CF4 Decomposition at Room T | 9 | 풀분석 추천 | 9 | 풀분석 추천 | +0 | CF4, catalytic decomposition, Al, nonthermal plasma | CF₄ 직접 언급 및 Lewis acid 기반 촉매(Al)를 사용한 비열 플라즈마-촉매 결합 연구로 높은 관련성을 가짐. |
| Hydrolysis of Hexafluoroethane (PFC-116) over Alumina–zirconia Catalysts Prepare | 7 | 풀분석 추천 | 7 | 풀분석 추천 | +0 | Hexafluoroethane, hydrolysis, Alumina-zirconia, catalysts | C₂F₆는 CF₄와 유사한 메커니즘을 가지며, Al-Zr 조합의 촉매 가수분해 연구이므로 높은 관련성을 가집니다. |
| Photo-catalytic destruction of tetracycline antibiotics using terbium and mangan | 1 | 휴지통 | 1 | 휴지통 | +0 | tetracycline antibiotics, photocatalytic | 반응물(테트라사이클린)이 CF₄와 완전히 다르며, 촉매 메커니즘도 무관합니다. |
| Catalytic thermal decomposition of tetrafluoromethane (CF4): A review | - | 풀분석 추천 | 10 | 풀분석 추천 | - | CF4, catalytic-thermal decomposition, review | CF₄ 직접 언급, 촉매 분해/가수분해 메커니즘 리뷰이며, Lewis acid 기반 촉매 시스템에 대한 포괄적인 논의가 예상됨. |
| Highly Efficient Decomposition of Perfluorocarbons for over 1000 Hours via Activ | - | 풀분석 추천 | 10 | 풀분석 추천 | - | CF4, catalytic hydrolysis, Ga/Al2O3, defluorination, active site regeneration | CF₄ 직접 분해에 대해 Lewis acid 기반의 Ga/Al 산화물 촉매를 사용하고, 활성점 재생 메커니즘까지 상세히 다루고 있어 가장 높은 관련도를 가집니다. |
| Optimization of Sol–Gel Catalysts with Zirconium and Tungsten Additives for Enha | - | 풀분석 추천 | 10 | 풀분석 추천 | - | CF4, catalytic decomposition, ZrO2, Al2O3, WO3 | CF₄ 직접 분해를 목표로 하며, Lewis acid 기반의 Al/Zr/W 조합 촉매 설계 및 성능 최적화에 대한 구체적인 메커니즘 연구가 포함됨. |
| Preliminary Study on Plasma-Catalyst Combination for CF4 Removal | - | 자동 발견 | 5 | 자동 발견 | - | CF4, plasma-catalyst (title only) | abstract 부재로 메커니즘 확인 불가. 제목에 CF4와 catalyst가 모두 명시되어 0층 룰에 따라 최대 5점 부여. |
| Promoting C F bond activation by Ce/Al2O3 catalyst for CF4 plasma-catalytic deco | - | 풀분석 추천 | 9 | 풀분석 추천 | - | CF4, catalytic decomposition, Ce/Al2O3, plasma-catalytic | CF₄ 직접 언급 및 Lewis acid 기반 촉매(Ce/Al₂O₃)를 이용한 플라즈마-촉매 분해 메커니즘이 명확하게 제시됨. |
| Destruction and removal of nitrogen trifluoride (NF3), sulfur hexafluoride (SF6) | - | - | 3 | 휴지통 | - | NF3, SF6, CF4, molten-metal | 반응 매체로 용융 금속(molten metal)을 사용했으며, 촉매 가수분해 메커니즘이 아닌 열적/물리적 제거 방식이므로 점수가 낮게 책정됨. |
