import warnings

from huggingface_hub import hf_hub_download
from safetensors.torch import load_file

from .base import CHECKPOINT_MAPPING, POST_LOAD_CALLBACKS, STATE_DICT_KEY_MAPPING, LightningIRModel
from .models import ColConfig, DprConfig, MonoConfig, SpladeConfig


def _map_colbert_marker_tokens(model: LightningIRModel) -> LightningIRModel:
    config = model.config
    query_token_id = config.vocab_size
    doc_token_id = config.vocab_size + 1
    model.resize_token_embeddings(config.vocab_size + 2, 8)
    embeddings = model.embeddings.word_embeddings.weight.data
    embeddings[query_token_id] = embeddings[1]  # [unused0]
    embeddings[doc_token_id] = embeddings[2]  # [unused1]
    return model


def _map_moderncolbert_marker_tokens(model: LightningIRModel) -> LightningIRModel:
    config = model.config
    query_token_id = config.vocab_size
    doc_token_id = config.vocab_size + 1
    model.resize_token_embeddings(config.vocab_size + 2, 8)
    embeddings = model.embeddings.tok_embeddings.weight.data
    embeddings[query_token_id] = embeddings[50368]  # [unused0]
    embeddings[doc_token_id] = embeddings[50369]  # [unused1]

    path = hf_hub_download("lightonai/GTE-ModernColBERT-v1", filename="model.safetensors", subfolder="1_Dense")
    state_dict = load_file(path)
    state_dict["weight"] = state_dict.pop("linear.weight")
    model.projection.load_state_dict(state_dict)
    return model


def _map_mono_t5_weights(model: LightningIRModel) -> LightningIRModel:
    # [1176, 6136] true, false
    warnings.warn(
        "The above warning, that the linear layer is not initialized, is expected and can be ignored."
        "The weights are initialized separately."
    )
    model.linear.weight.data = model.shared.weight.data[[6136, 1176]]
    return model


def _map_rank_t5_weights(model: LightningIRModel) -> LightningIRModel:
    # 32089 <extra_id_10>
    warnings.warn(
        "The above warning, that the linear layer is not initialized, is expected and can be ignored."
        "The weights are initialized separately."
    )
    model.linear.weight.data = model.shared.weight.data[[32089]]
    return model


MONO_T5_PATTERN = "Query: {query} Document: {doc} Relevant:"
RANK_T5_PATTERN = "Query: {query} Document: {doc}"


def _register_external_models():
    CHECKPOINT_MAPPING.update(
        {
            "colbert-ir/colbertv2.0": ColConfig(
                query_length=32,
                doc_length=184,
                add_marker_tokens=True,
                normalize=True,
                query_expansion=True,
                doc_mask_scoring_tokens="punctuation",
            ),
            "lightonai/GTE-ModernColBERT-v1": ColConfig(
                query_length=32,
                doc_length=296,
                add_marker_tokens=True,
                normalize=True,
                query_expansion=True,
                projection="linear_no_bias",
                doc_mask_scoring_tokens="punctuation",
            ),
            "naver/splade-v3": SpladeConfig(),
            "sentence-transformers/msmarco-bert-base-dot-v5": DprConfig(
                projection=None, query_pooling_strategy="mean", doc_pooling_strategy="mean"
            ),
            "sentence-transformers/msmarco-distilbert-dot-v5": DprConfig(
                projection=None, query_pooling_strategy="mean", doc_pooling_strategy="mean"
            ),
            "sentence-transformers/msmarco-MiniLM-L-6-v3": DprConfig(
                projection=None, query_pooling_strategy="mean", doc_pooling_strategy="mean"
            ),
            "castorini/monot5-base-msmarco-10k": MonoConfig(scoring_strategy="mono", tokenizer_pattern=MONO_T5_PATTERN),
            "castorini/monot5-base-msmarco": MonoConfig(scoring_strategy="mono", tokenizer_pattern=MONO_T5_PATTERN),
            "castorini/monot5-large-msmarco-10k": MonoConfig(
                scoring_strategy="mono", tokenizer_pattern=MONO_T5_PATTERN
            ),
            "castorini/monot5-large-msmarco": MonoConfig(scoring_strategy="mono", tokenizer_pattern=MONO_T5_PATTERN),
            "castorini/monot5-3b-msmarco-10k": MonoConfig(scoring_strategy="mono", tokenizer_pattern=MONO_T5_PATTERN),
            "castorini/monot5-3b-msmarco": MonoConfig(scoring_strategy="mono", tokenizer_pattern=MONO_T5_PATTERN),
            "Soyoung97/RankT5-base": MonoConfig(scoring_strategy="rank", tokenizer_pattern=RANK_T5_PATTERN),
            "Soyoung97/RankT5-large": MonoConfig(scoring_strategy="rank", tokenizer_pattern=RANK_T5_PATTERN),
            "Soyoung97/RankT5-3b": MonoConfig(scoring_strategy="rank", tokenizer_pattern=RANK_T5_PATTERN),
            "castorini/monobert-large-msmarco-finetune-only": MonoConfig(
                scoring_strategy="mono", linear_bias=True, pooling_strategy="bert_pool"
            ),
            "castorini/monobert-large-msmarco": MonoConfig(
                scoring_strategy="mono", linear_bias=True, pooling_strategy="bert_pool"
            ),
        }
    )
    STATE_DICT_KEY_MAPPING.update(
        {
            "colbert-ir/colbertv2.0": [("linear.weight", "bert.projection.weight")],
            "castorini/monobert-large-msmarco-finetune-only": [
                ("classifier.weight", "bert.linear.weight"),
                ("classifier.bias", "bert.linear.bias"),
                ("bert.pooler.dense.weight", "bert.bert_pool.0.weight"),
                ("bert.pooler.dense.bias", "bert.bert_pool.0.bias"),
            ],
            "castorini/monobert-large-msmarco": [
                ("classifier.weight", "bert.linear.weight"),
                ("classifier.bias", "bert.linear.bias"),
                ("bert.pooler.dense.weight", "bert.bert_pool.0.weight"),
                ("bert.pooler.dense.bias", "bert.bert_pool.0.bias"),
            ],
        }
    )
    POST_LOAD_CALLBACKS.update(
        {
            "colbert-ir/colbertv2.0": _map_colbert_marker_tokens,
            "lightonai/GTE-ModernColBERT-v1": _map_moderncolbert_marker_tokens,
            "castorini/monot5-base-msmarco-10k": _map_mono_t5_weights,
            "castorini/monot5-base-msmarco": _map_mono_t5_weights,
            "castorini/monot5-large-msmarco-10k": _map_mono_t5_weights,
            "castorini/monot5-large-msmarco": _map_mono_t5_weights,
            "castorini/monot5-3b-msmarco-10k": _map_mono_t5_weights,
            "castorini/monot5-3b-msmarco": _map_mono_t5_weights,
            "Soyoung97/RankT5-base": _map_rank_t5_weights,
            "Soyoung97/RankT5-large": _map_rank_t5_weights,
            "Soyoung97/RankT5-3b": _map_rank_t5_weights,
        }
    )
