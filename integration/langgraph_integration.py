"""
LangGraph集成示例

演示如何将FairyExecutor集成到LangGraph工作流中
"""

import asyncio
from pathlib import Path
from typing import TypedDict, Annotated, Sequence
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from Executor import ExecutorConfig, FairyExecutor, ExecutionOutput
from Executor.logger import setup_logger

# 注意：需要安装 langgraph
# pip install langgraph langchain-core

try:
    from langgraph.graph import StateGraph, END
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    print("警告: LangGraph未安装，请运行: pip install langgraph langchain-core")


# ==================== 状态定义 ====================

class AgentState(TypedDict):
    """Agent状态"""
    messages: Annotated[Sequence[BaseMessage], "对话历史"]
    task: str
    plan: list[str]
    current_step: int
    execution_results: list[ExecutionOutput]
    completed: bool


# ==================== Agent节点 ====================

class TestAutomationAgent:
    """自动化测试Agent

    使用LangGraph编排测试流程，使用FairyExecutor执行移动端操作
    """

    def __init__(self, executor: FairyExecutor):
        self.executor = executor

    async def plan_node(self, state: AgentState) -> AgentState:
        """规划节点：将任务分解为步骤"""
        task = state["task"]

        # 这里可以使用LLM生成计划
        # 为了演示，我们使用简单的硬编码计划
        if "游戏" in task:
            plan = [
                "点击游戏按钮",
                "等待页面加载",
                "向下滚动查看游戏列表",
                "点击第一个游戏"
            ]
        else:
            plan = ["执行任务"]

        state["plan"] = plan
        state["current_step"] = 0
        state["messages"].append(AIMessage(content=f"已生成计划，共{len(plan)}步"))

        return state

    async def execute_node(self, state: AgentState) -> AgentState:
        """执行节点：执行当前步骤"""
        plan = state["plan"]
        current_step = state["current_step"]

        if current_step >= len(plan):
            state["completed"] = True
            return state

        instruction = plan[current_step]
        state["messages"].append(AIMessage(content=f"执行步骤 {current_step + 1}: {instruction}"))

        # 使用FairyExecutor执行
        result = await self.executor.execute(
            instruction=instruction,
            plan_context={
                "overall_plan": state["task"],
                "current_sub_goal": instruction
            },
            historical_actions=[
                action
                for r in state["execution_results"]
                for action in r.actions_taken
            ]
        )

        state["execution_results"].append(result)
        state["current_step"] += 1

        if result.success:
            state["messages"].append(AIMessage(content=f"✓ 步骤完成: {result.action_expectation}"))
        else:
            state["messages"].append(AIMessage(content=f"✗ 步骤失败: {result.error}"))
            state["completed"] = True  # 失败则停止

        return state

    async def check_node(self, state: AgentState) -> AgentState:
        """检查节点：验证执行结果"""
        last_result = state["execution_results"][-1] if state["execution_results"] else None

        if last_result and last_result.success:
            # 这里可以添加更复杂的验证逻辑
            # 例如：检查屏幕状态、验证UI元素等
            state["messages"].append(AIMessage(content="验证通过"))
        else:
            state["messages"].append(AIMessage(content="验证失败"))

        return state

    def should_continue(self, state: AgentState) -> str:
        """决定是否继续执行"""
        if state["completed"]:
            return "end"
        elif state["current_step"] >= len(state["plan"]):
            return "end"
        else:
            return "execute"

    def build_graph(self) -> StateGraph:
        """构建LangGraph工作流"""
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("plan", self.plan_node)
        workflow.add_node("execute", self.execute_node)
        workflow.add_node("check", self.check_node)

        # 添加边
        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "execute")
        workflow.add_edge("execute", "check")
        workflow.add_conditional_edges(
            "check",
            self.should_continue,
            {
                "execute": "execute",
                "end": END
            }
        )

        return workflow.compile()


# ==================== 使用示例 ====================

async def langgraph_example():
    """LangGraph集成示例"""

    if not LANGGRAPH_AVAILABLE:
        print("请先安装LangGraph: pip install langgraph langchain-core")
        return

    # 1. 配置日志
    setup_logger(log_level="INFO")

    # 2. 创建FairyExecutor
    config = ExecutorConfig.from_env()
    executor = FairyExecutor(config)

    # 3. 创建测试Agent
    agent = TestAutomationAgent(executor)
    graph = agent.build_graph()

    # 4. 运行测试任务
    initial_state = AgentState(
        messages=[HumanMessage(content="请帮我测试游戏页面")],
        task="测试游戏页面的浏览功能",
        plan=[],
        current_step=0,
        execution_results=[],
        completed=False
    )

    print("开始执行自动化测试...")
    final_state = await graph.ainvoke(initial_state)

    # 5. 输出结果
    print("\n测试完成！")
    print(f"执行步骤数: {len(final_state['execution_results'])}")
    print(f"\n对话历史:")
    for msg in final_state["messages"]:
        print(f"  {msg.content}")

    print(f"\n执行结果:")
    for i, result in enumerate(final_state["execution_results"], 1):
        print(f"  步骤 {i}: {'成功' if result.success else '失败'}")
        print(f"    动作: {result.actions_taken}")
        print(f"    输出: {result.output_files.get('result', 'N/A')}")

    return final_state


async def simple_integration():
    """简单集成示例（不使用LangGraph的完整功能）"""

    setup_logger(log_level="INFO")
    config = ExecutorConfig.from_env()
    executor = FairyExecutor(config)

    # 定义测试流程
    test_steps = [
        {
            "name": "打开游戏页面",
            "instruction": "点击游戏按钮",
            "verify": lambda result: "游戏" in result.action_expectation
        },
        {
            "name": "浏览游戏列表",
            "instruction": "向下滚动",
            "verify": lambda result: result.success
        },
        {
            "name": "选择游戏",
            "instruction": "点击第一个游戏",
            "verify": lambda result: "点击" in result.action_thought
        }
    ]

    # 执行测试
    results = []
    for step in test_steps:
        print(f"\n执行: {step['name']}")

        result = await executor.execute(
            instruction=step["instruction"],
            plan_context={
                "overall_plan": "游戏页面测试",
                "current_sub_goal": step["name"]
            }
        )

        results.append(result)

        # 验证结果
        if step["verify"](result):
            print(f"✓ {step['name']} - 通过")
        else:
            print(f"✗ {step['name']} - 失败")
            break

    return results


if __name__ == "__main__":
    # 运行LangGraph示例
    if LANGGRAPH_AVAILABLE:
        asyncio.run(langgraph_example())
    else:
        # 运行简单集成示例
        asyncio.run(simple_integration())
