import sys


def train_dpo(jsonl_path: str, base_model: str, out_dir: str, epochs: int = 1) -> None:
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import DPOConfig, DPOTrainer

    ds = load_dataset("json", data_files=jsonl_path, split="train")
    if len(ds) == 0:
        raise ValueError(f"no preference pairs in {jsonl_path}")
    tok = AutoTokenizer.from_pretrained(base_model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(base_model)
    args = DPOConfig(output_dir=out_dir, num_train_epochs=epochs, per_device_train_batch_size=2, report_to="none", save_strategy="no")
    trainer = DPOTrainer(model=model, args=args, train_dataset=ds, processing_class=tok)
    trainer.train()
    trainer.save_model(out_dir)
    tok.save_pretrained(out_dir)       

if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: python -m app.rl.dpo_train <pairs.jsonl> <base_model> <out_dir>")
    train_dpo(*sys.argv[1:])
