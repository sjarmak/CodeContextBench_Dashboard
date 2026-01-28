# Benchmark Analysis: locobench_50_tasks_20260124_225159

Generated: 2026-01-25T16:37:01.047398Z

## Summary

| MCP Mode | Tasks | Mean Reward | Min | Max | Input Tokens | Output Tokens |
|----------|-------|-------------|-----|-----|--------------|---------------|
| baseline | 51 | 0.4390 | 0.0000 | 0.5513 | 7,809,749 | 2,227 |
| deepsearch_hybrid | 51 | 0.4431 | 0.0000 | 0.5707 | 51,115,643 | 23,433 |

## MCP vs Baseline Comparison

### deepsearch_hybrid
- Mean Reward Delta: +0.0041 (+0.9%)
- Token Usage Delta: +43,305,894 input, +21,206 output

## Per-Task Results

### baseline

| Task | Reward | Duration (s) | Input Tokens |
|------|--------|--------------|--------------|
| python_game_engine_expert_032_cross_file_refactori | 0.5513 | 551.7 | 0 |
| c_blockchain_nft_expert_071_architectural_understa | 0.5435 | 231.7 | 0 |
| javascript_web_social_expert_073_architectural_und | 0.5141 | 247.9 | 0 |
| c_ml_nlp_expert_017_architectural_understanding_ex | 0.5093 | 181.9 | 1,618,899 |
| c_api_microservice_expert_080_architectural_unders | 0.5090 | 181.2 | 0 |
| c_blockchain_nft_expert_071_cross_file_refactoring | 0.5082 | 661.3 | 0 |
| csharp_data_etl_expert_047_architectural_understan | 0.5015 | 362.4 | 0 |
| java_api_rest_expert_006_architectural_understandi | 0.4982 | 204.4 | 1,433,455 |
| c_api_graphql_expert_079_architectural_understandi | 0.4911 | 269.0 | 0 |
| csharp_ml_training_expert_087_architectural_unders | 0.4871 | 206.9 | 0 |
| c_api_microservice_expert_080_cross_file_refactori | 0.4820 | 187.4 | 0 |
| java_mobile_social_expert_058_architectural_unders | 0.4811 | 217.2 | 0 |
| c_fintech_payment_expert_065_architectural_underst | 0.4783 | 349.1 | 0 |
| c_api_graphql_expert_079_cross_file_refactoring_ex | 0.4781 | 356.7 | 0 |
| java_web_ecommerce_expert_036_architectural_unders | 0.4719 | 315.3 | 0 |
| python_fintech_payment_expert_029_architectural_un | 0.4698 | 259.7 | 0 |
| typescript_desktop_productivity_expert_055_archite | 0.4672 | 261.6 | 0 |
| javascript_blockchain_nft_expert_035_architectural | 0.4617 | 178.2 | 1,813,943 |
| cpp_web_dashboard_expert_039_architectural_underst | 0.4599 | 241.2 | 0 |
| csharp_web_blog_expert_076_architectural_understan | 0.4506 | 156.6 | 0 |
| ... and 31 more tasks | | | |

### deepsearch_hybrid

| Task | Reward | Duration (s) | Input Tokens |
|------|--------|--------------|--------------|
| java_api_rest_expert_006_architectural_understandi | 0.5707 | 536.6 | 566,617 |
| csharp_data_etl_expert_047_architectural_understan | 0.5240 | 1112.6 | 1,691,225 |
| c_blockchain_nft_expert_071_architectural_understa | 0.5162 | 640.4 | 712,865 |
| c_blockchain_nft_expert_071_cross_file_refactoring | 0.5128 | 338.9 | 1,549,001 |
| c_ml_nlp_expert_017_architectural_understanding_ex | 0.5122 | 495.2 | 1,099,084 |
| java_web_ecommerce_expert_036_architectural_unders | 0.5089 | 593.4 | 2,257,010 |
| c_api_microservice_expert_080_cross_file_refactori | 0.5054 | 205.0 | 818,882 |
| cpp_system_security_expert_064_architectural_under | 0.4967 | 472.3 | 557,508 |
| csharp_ml_training_expert_087_architectural_unders | 0.4890 | 318.6 | 408,521 |
| java_web_ecommerce_expert_000_architectural_unders | 0.4837 | 285.8 | 2,525,722 |
| javascript_blockchain_nft_expert_035_architectural | 0.4833 | 480.1 | 1,916,836 |
| java_mobile_social_expert_058_architectural_unders | 0.4811 | 500.1 | 978,811 |
| python_desktop_development_expert_021_architectura | 0.4777 | 571.2 | 662,549 |
| typescript_desktop_productivity_expert_055_archite | 0.4742 | 191.8 | 1,614,660 |
| csharp_blockchain_defi_expert_070_architectural_un | 0.4734 | 713.5 | 794,384 |
| c_fintech_payment_expert_065_architectural_underst | 0.4703 | 1007.5 | 1,228,896 |
| javascript_ml_nlp_expert_053_architectural_underst | 0.4686 | 618.3 | 704,193 |
| cpp_web_dashboard_expert_039_architectural_underst | 0.4675 | 705.9 | 1,421,776 |
| c_api_graphql_expert_079_architectural_understandi | 0.4669 | 616.9 | 2,475,039 |
| csharp_data_warehouse_expert_012_bug_investigation | 0.4665 | 435.1 | 584,066 |
| ... and 31 more tasks | | | |
