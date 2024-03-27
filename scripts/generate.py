#!/usr/bin/env python3

from vllm import LLM

llm = LLM(model='/data/vicuna/', gpu_memory_utilization=0.8)
print(llm.generate('the quick brown fox'))
