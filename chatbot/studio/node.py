from dotenv import load_dotenv
load_dotenv()
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from prompts import MODEL_SYSTEM_MESSAGE, question_relevanted
from typing import Literal
from pydantic import Field
from langchain_community.vectorstores import FAISS
from utils import State

def detect_qtype(state:State, llm):
    response = llm.invoke([SystemMessage(content=question_relevanted)]+[HumanMessage(content=state['messages'][-1].content)])
    return {"relevant": response.content}

def search_llm(state, llm):
    response = llm.invoke([SystemMessage(content=MODEL_SYSTEM_MESSAGE)]+state["messages"])
    return {"messages": [response]}

def search_vector_db(state, llm, embeddings):
    vector_store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    results = vector_store.similarity_search(query=state["messages"][-1].content,k=1)
    if(len(results)==0):
        return {"messages": state["messages"][-1]}
    return {"messages": [AIMessage(content = results[0].metadata['source'],additional_kwargs={"is_link": True})]}

def terminate(state, llm):
    response = llm.invoke([SystemMessage(content=MODEL_SYSTEM_MESSAGE)]+state['messages'])
    return {"messages": [AIMessage(content = response.content)]}
