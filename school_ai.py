from typing import TypedDict
from langgraph.graph import StateGraph
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

# FREE AI model
llm = ChatGroq(
    model="llama-3.1-8b-instant", api_key=("GROQ_KEY")
)

# State Schema


class StudentState(TypedDict, total=False):
    question: str
    answer: str

# Node 1


def get_question(state):
    question = input("Ask your question: ")
    return {"question": question}

# Node 2


def ask_ai(state):
    response = llm.invoke([HumanMessage(content=state["question"])])
    return {"answer": response.content}

# Node 3


def show_answer(state):
    print("\n📘 AI Teacher Says:\n")
    print(state["answer"])
    return {}


builder = StateGraph(StudentState)

builder.add_node("input", get_question)
builder.add_node("chatgpt", ask_ai)
builder.add_node("output", show_answer)

builder.add_edge("input", "chatgpt")
builder.add_edge("chatgpt", "output")

builder.set_entry_point("input")

graph = builder.compile()

graph.invoke({})