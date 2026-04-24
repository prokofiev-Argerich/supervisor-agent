from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

load_dotenv()
import os

print("OPENAI_BASE_URL =", os.getenv("OPENAI_BASE_URL"))
print("OPENAI_MODEL =", os.getenv("OPENAI_MODEL"))

llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
    temperature=0.7,
)



class AgentState(TypedDict):
    topic: str
    outline: str
    draft: str


def planner_node(state: AgentState) -> dict:
    topic = state["topic"]
    prompt = (
        "你是一位资深学术教授。请根据以下主题，输出一个包含 3 个核心章节的 Markdown 格式大纲。\n"
        "每个章节需要有标题和 2-3 个要点。\n\n"
        f"主题：{topic}"
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"outline": response.content}


def writer_node(state: AgentState) -> dict:
    topic = state["topic"]
    outline = state["outline"]
    prompt = (
        "你是一位专业的学术撰稿人。请根据以下大纲，严格撰写第一章节的内容，约 300 字。\n"
        "要求语言严谨、逻辑清晰、学术风格。\n\n"
        f"主题：{topic}\n\n"
        f"大纲：\n{outline}"
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"draft": response.content}


graph = StateGraph(AgentState)
graph.add_node("planner", planner_node)
graph.add_node("writer", writer_node)

graph.add_edge(START, "planner")
graph.add_edge("planner", "writer")
graph.add_edge("writer", END)

app = graph.compile()


if __name__ == "__main__":
    result = app.invoke({"topic": "大语言模型在医疗诊断中的应用与挑战", "outline": "", "draft": ""})

    print("=" * 60)
    print("📋 大纲 (Outline)")
    print("=" * 60)
    print(result["outline"])
    print()
    print("=" * 60)
    print("📝 初稿 (Draft - 第一章节)")
    print("=" * 60)
    print(result["draft"])
