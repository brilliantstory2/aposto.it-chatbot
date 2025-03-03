from dotenv import load_dotenv
load_dotenv()
import os
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from prompts import MODEL_SYSTEM_MESSAGE, question_relevanted, promotion_prompt, workshop_prompt
from typing import Literal
from pydantic import Field
from langchain_community.vectorstores import FAISS
from langchain.prompts import PromptTemplate
from utils import State

faiss_db = os.environ["FAISS_VECTOR_DB"]

def detect_qtype(state:State, llm):
    response = llm.invoke([SystemMessage(content=question_relevanted)]+[HumanMessage(content=state['messages'][-1].content)])
    return {"relevant": response.content}

def search_llm(state, llm):
    response = llm.invoke([SystemMessage(content=MODEL_SYSTEM_MESSAGE)]+state["messages"])
    return {"messages": [response]}

def find_link(state, llm, embeddings):
    vector_store = FAISS.load_local(faiss_db, embeddings, allow_dangerous_deserialization=True)
    results = vector_store.similarity_search(query=state["messages"][-1].content,k=1)
    if(len(results)==0):
        return {"messages": state["messages"][-1]}
    return {"messages": [AIMessage(content = results[0].metadata['source'],additional_kwargs={"is_link": True})]}

def terminate(state, llm):
    response = llm.invoke([SystemMessage(content=MODEL_SYSTEM_MESSAGE)]+state['messages'])
    return {"messages": [AIMessage(content = response.content)]}

def promotion(state, llm, embeddings):
    vector_store = FAISS.load_local(faiss_db, embeddings, allow_dangerous_deserialization=True)
    results = vector_store.similarity_search(query=state["messages"][-1].content,k=1)
    context = results[0].metadata["source"]
    formatted_prompt = promotion_prompt.format(question=state["messages"][-1], context=context)
    response = llm.invoke([SystemMessage(content=formatted_prompt)]+[HumanMessage(content=state['messages'][-1].content)])
    return {"messages": [AIMessage(content = response.content), AIMessage(content = context,additional_kwargs={"is_link": True})]}

def workshop(state, llm):
    response = llm.invoke([SystemMessage(content=workshop_prompt)]+[HumanMessage(content=state['messages'][-1].content)])
    return {"messages": [AIMessage(content = response.content, additional_kwargs={"geolocation": True})]}