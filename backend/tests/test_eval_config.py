from eval.gate import load_eval_config

def test_thresholds_present():
    c = load_eval_config("eval/config.yaml")
    assert c.thresholds["faithfulness"] >= 0.8 and "rag" in c.datasets
