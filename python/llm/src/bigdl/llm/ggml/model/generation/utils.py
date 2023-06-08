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

# This would makes sure Python is aware there is more than one sub-package within bigdl,
# physically located elsewhere.
# Otherwise there would be module not found error in non-pip's setting as Python would
# only search the first bigdl package and end up finding only one sub-package.


from typing import Optional, Union, Sequence, List
from bigdl.llm.utils.common import invalidInputError


class GenerationMixin:
    """
    A class containing all functions for auto-regressive text generation

    Pass custom parameter values to 'generate' .
    """
    def tokenize(self, text: str, add_bos: bool = True) -> List[int]:
        '''
        Decode the id to words

        :param text: The text to be tokenized
        :param add_bos:

        :return: list of ids that indicates the tokens
        '''
        if isinstance(text, str):
            bstr = text.encode()
        else:
            bstr = text
        return self._tokenize(bstr, add_bos)

    def decode(self, tokens: List[int]) -> str:
        '''
        Decode the id to words

        :param tokens: list of ids that indicates the tokens, mostly generated by generate
        :return: decoded string
        '''
        return self.detokenize(tokens).decode()

    def generate(
        self,
        inputs: Optional[Sequence[int]]=None,
        max_new_tokens: int = 128,
        top_k: int = 40,
        top_p: float = 0.95,
        temperature: float = 0.80,
        repetition_penalty: float = 1.1,
        reset: bool = True,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        tfs_z: float = 1.0,
        mirostat_mode: int = 0,
        mirostat_tau: float = 5.0,
        mirostat_eta: float = 0.1,
        stop: Optional[Union[str, List[str]]]=[],  # TODO: rebase to support stopping_criteria
        **kwargs,
    ) -> Union[Optional[Sequence[int]], None]:
        # TODO: modify docs
        """Create a generator of tokens from a prompt.

        Examples:
            >>> llm = AutoModelForCausalLM.from_pretrained("gpt4all-model-q4_0.bin",
                                                           model_family="llama")
            >>> tokens = llm.tokenize("Q: Tell me something about Intel. A:")
            >>> tokens_id = llm.generate(tokens, max_new_tokens=32)
            >>> llm.decode(tokens_id)

        Args:
            tokens: The prompt tokens.
            top_k: The top-k sampling parameter.
            top_p: The top-p sampling parameter.
            temp: The temperature parameter.
            repeat_penalty: The repeat penalty parameter.
            reset: Whether to reset the model state.

        Yields:
            The generated tokens.
        """
        tokens = self._generate(tokens=inputs,
                                top_k=top_k,
                                top_p=top_p,
                                temp=temperature,
                                repeat_penalty=repetition_penalty,
                                reset=reset,
                                frequency_penalty=frequency_penalty,
                                presence_penalty=presence_penalty,
                                tfs_z=tfs_z,
                                mirostat_mode=mirostat_mode,
                                mirostat_tau=mirostat_tau,
                                mirostat_eta=mirostat_eta,
                                **kwargs)
        res_list = []
        word_count = 0
        for token in tokens:
            if word_count > max_new_tokens:
                break
            res_list.append(token)
            word_count += 1
        return res_list
