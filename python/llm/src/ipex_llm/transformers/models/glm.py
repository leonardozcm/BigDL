#
# Copyright 2016 The BigDL Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This file is adapted from
# https://github.com/huggingface/transformers/blob/main/src/transformers/models/glm/modeling_glm.py
#
# which is licensed under Apache License 2.0:
#
# Copyright 2024 The GLM & ZhipuAI team and HuggingFace Inc. team. All rights reserved.
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import torch

from typing import Optional, Tuple
from transformers.cache_utils import Cache
from transformers.models.glm.modeling_glm import apply_rotary_pos_emb
from ipex_llm.transformers.kv import DynamicNormalCache, DynamicFp8Cache
from ipex_llm.transformers.models.common import merge_qkv_base
from ipex_llm.transformers.models.common import scaled_dot_product_attention
from ipex_llm.transformers.models.utils import make_cache_contiguous_inplaced
from ipex_llm.transformers.models.utils import use_quantize_kv_cache


def merge_qkv(module: torch.nn.Module):
    merge_qkv_base(module, "GlmAttention")
    merge_qkv_base(module, "SiglipAttention")


def split_mlp(module: torch.nn.Module):
    if module.__class__.__name__ == "GlmMLP":
        gate_weight, up_weight = module.gate_up_proj.weight.data.chunk(2, dim=0)

        gate_proj = torch.nn.Linear(0, 0, bias=False)
        gate_proj.weight = torch.nn.Parameter(gate_weight, requires_grad=False)
        gate_proj.in_features = gate_weight.size(1)
        gate_proj.out_features = gate_weight.size(0)

        up_proj = torch.nn.Linear(0, 0, bias=False)
        up_proj.weight = torch.nn.Parameter(up_weight, requires_grad=False)
        up_proj.in_features = up_weight.size(1)
        up_proj.out_features = up_weight.size(0)

        module.gate_proj = gate_proj
        module.up_proj = up_proj

        del module.gate_up_proj

        # rename activation function
        module.act_fn = module.activation_fn


def glm_attention_forward(
    self,
    hidden_states: torch.Tensor,
    attention_mask: Optional[torch.Tensor] = None,
    position_ids: Optional[torch.LongTensor] = None,
    past_key_value: Optional[Cache] = None,
    output_attentions: bool = False,
    use_cache: bool = False,
    cache_position: Optional[torch.LongTensor] = None,
    position_embeddings: Optional[Tuple[torch.Tensor, torch.Tensor]]=None,
    **kwargs,
):
    bsz, q_len, _ = hidden_states.size()

    qkv = self.qkv_proj(hidden_states)
    qkv = qkv.view(bsz, q_len, self.num_heads + 2 * self.num_key_value_heads, self.head_dim)
    qkv = qkv.transpose(1, 2)
    query_states, key_states, value_states = qkv.split([self.num_heads,
                                                        self.num_key_value_heads,
                                                        self.num_key_value_heads], dim=1)

    cos, sin = position_embeddings
    if query_states.device.type == "xpu":
        import xe_addons
        make_cache_contiguous_inplaced(cos, sin)
        xe_addons.rotary_two_with_cache_inplaced(query_states, key_states, cos, sin, True)
    else:
        query_states, key_states = apply_rotary_pos_emb(query_states, key_states, cos, sin)

    # sin and cos are specific to RoPE models; cache_position needed for the static cache
    cache_kwargs = {"sin": sin, "cos": cos, "cache_position": cache_position}
    key_states, value_states = past_key_value.update(key_states, value_states,
                                                     self.layer_idx, cache_kwargs)

    attn_weights = None
    attn_output = scaled_dot_product_attention(
        query_states, key_states, value_states,
        attention_mask, q_len == key_states.size(2), self.scaling
    )

    attn_output = attn_output.transpose(1, 2).contiguous()
    attn_output = attn_output.reshape(bsz, q_len, self.hidden_size)

    attn_output = self.o_proj(attn_output)

    if not output_attentions:
        attn_weights = None
    return attn_output, attn_weights, past_key_value


def glm_model_forward_wrapper(origin_forward):
    def glm_model_forward(
        self,
        input_ids: torch.LongTensor = None,
        images: torch.Tensor = None,
        attention_mask: Optional[torch.Tensor] = None,
        position_ids: Optional[torch.LongTensor] = None,
        past_key_values: Optional[Cache] = None,
        inputs_embeds: Optional[torch.FloatTensor] = None,
        use_cache: Optional[bool] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None,
        cache_position: Optional[torch.LongTensor] = None,
        **kwargs,
    ):
        # ipex-llm changes start
        # IPEX-LLM OPT: kv cache and quantize kv cache
        inputs = input_ids if input_ids is not None else inputs_embeds
        use_cache = use_cache if use_cache is not None else self.config.use_cache
        use_cache = use_cache or inputs.device.type == 'xpu'
        use_quantize_kv = use_quantize_kv_cache(self.layers[0].mlp.down_proj, inputs,
                                                self.config.num_attention_heads //
                                                self.config.num_key_value_heads)

        if use_cache:
            if use_quantize_kv and not isinstance(past_key_values, DynamicFp8Cache):
                past_key_values = DynamicFp8Cache.from_legacy_cache(past_key_values)
            elif not use_quantize_kv and not isinstance(past_key_values, DynamicNormalCache):
                past_key_values = DynamicNormalCache.from_legacy_cache(past_key_values)
        # ipex-llm changes end

        return origin_forward(
            self=self,
            input_ids=input_ids,
            images=images,
            attention_mask=attention_mask,
            position_ids=position_ids,
            past_key_values=past_key_values,
            inputs_embeds=inputs_embeds,
            use_cache=use_cache,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
            cache_position=cache_position,
            **kwargs,
        )

    return glm_model_forward