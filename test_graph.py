import asyncio
import sys
from evaluation.evaluator import _build_state, TEST_CASES
from agents.graph import graph

async def run():
    state = _build_state(TEST_CASES[1])
    res = await graph.ainvoke(state)
    print('PATH:', [t.get('agent') for t in res.get('reasoning_trace',[])])
    print('NEXT:', res.get('next_agent'))
    print('ERROR:', res.get('error'))

if __name__ == '__main__':
    asyncio.run(run())
