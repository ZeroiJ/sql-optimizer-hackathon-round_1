"""Model loading utilities for Unsloth-based RL training."""

from unsloth import FastLanguageModel


def load_qwen_unsloth(max_seq_length: int = 2048):
    """Load Qwen2.5-Coder-7B-Instruct via Unsloth and apply LoRA adapters."""
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Qwen2.5-Coder-7B-Instruct",
        max_seq_length=max_seq_length,
        load_in_4bit=True,
        fast_inference=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=16,
        lora_dropout=0,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    return model, tokenizer
