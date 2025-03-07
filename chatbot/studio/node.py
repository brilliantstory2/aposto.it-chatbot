from dotenv import load_dotenv
load_dotenv()
import os
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from prompts import MODEL_SYSTEM_MESSAGE, format_prompt, check_qprompt, promotion_prompt, workshop_prompt, permission_prompt, location_prompt, display_workshops
from typing import Literal
from pydantic import Field
from langchain_community.vectorstores import FAISS
from langchain.prompts import PromptTemplate
from utils import State, Location
import requests

faiss_db = os.environ["FAISS_VECTOR_DB"]
get_workshop_api = os.environ["GET_WORKSHOP_API"]

def detect_qtype(state:State, llm):
    question_relevanted = check_qprompt.format(MODEL_SYSTEM_MESSAGE=MODEL_SYSTEM_MESSAGE)
    response = llm.invoke([SystemMessage(content=question_relevanted)]+[HumanMessage(content=state['messages'][-1].content)])
    return {"relevant": SystemMessage(content=response.content)}

def search_llm(state, llm):
    response = llm.invoke([SystemMessage(content=MODEL_SYSTEM_MESSAGE + format_prompt)]+state["messages"])
    return {"messages": [AIMessage(content = response.content, additional_kwargs={"complete": True})]}

def find_link(state, llm, embeddings):
    vector_store = FAISS.load_local(faiss_db, embeddings, allow_dangerous_deserialization=True)
    results = vector_store.similarity_search(query=state["messages"][-1].content,k=1)
    if(len(results)==0):
        return {"messages": state["messages"][-1]}
    return {"messages": [AIMessage(content = results[0].metadata['source'],additional_kwargs={"is_link": True, "complete":True})]}

def terminate(state, llm):
    response = llm.invoke([SystemMessage(content=MODEL_SYSTEM_MESSAGE)]+state['messages'])
    return {"messages": [AIMessage(content = response.content, additional_kwargs={"complete": True})]}

def promotion(state, llm, embeddings):
    vector_store = FAISS.load_local(faiss_db, embeddings, allow_dangerous_deserialization=True)
    retriever = vector_store.as_retriever()
    documents = retriever.invoke(state["messages"][-1].content)
    unique_list = []
    for doc in documents:
        if doc.metadata["source"] not in unique_list:
            unique_list.append(doc.metadata["source"])
    formatted_prompt = promotion_prompt.format(question=state["messages"][-1], documents=documents)
    response = llm.invoke([SystemMessage(content=formatted_prompt+format_prompt)])
    messages = [
        AIMessage(content=link, additional_kwargs={"is_link": True, "complete": True})
        for link in unique_list
    ]
    return {"messages": [AIMessage(content = response.content,additional_kwargs={"complete": True})]+messages}

def workshop(state, llm):
    formatted_prompt = workshop_prompt.format(messages=state["messages"])
    response = llm.invoke([SystemMessage(content=formatted_prompt)]+[HumanMessage(content=state['messages'][-1].content)])
    return {"is_location_provided": SystemMessage(content=response.content)}

def ask_permission(state, llm):
    response = llm.invoke([SystemMessage(content=permission_prompt)]+[HumanMessage(content=state['messages'][-1].content)])
    return {"messages": [AIMessage(content = response.content, additional_kwargs={"geolocation": True, "complete":True})]}

# def get_location(state, llm):
#     structured_llm = llm.with_structured_output(Location)
#     formatted_prompt = location_prompt.format(messages=state["messages"])
#     location = structured_llm.invoke([SystemMessage(content=formatted_prompt)])
#     return {"latitude": SystemMessage(content=location.latitude), "longitude": SystemMessage(content=location.longitude)}

def get_workshops(state: State, llm):
    # Extract location information using the structured LLM
    structured_llm = llm.with_structured_output(Location)
    formatted_prompt = location_prompt.format(messages=state["messages"])
    location = structured_llm.invoke([SystemMessage(content=formatted_prompt)])

    # Initialize parameters for the API request
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "workshop": True,
        "bodyWork": False,
        "tireRepairer": False,
        "distance": 15,
        "page": 1
    }

    workshops = []

    while True:
        response = requests.get(get_workshop_api, params=params)
        if response.status_code == 200:
            data = response.json()
            workshops += data.get("items", [])
            if params["page"] >= data.get("totalPages", 1):
                break
            params["page"] += 1
        else:
            return {"messages": [AIMessage(content="API call failed")]}

    formatted_prompt = display_workshops.format(workshops=workshops)
    response = llm.invoke([SystemMessage(content=formatted_prompt)]+state["messages"])

    return {"messages": [AIMessage(content=response.content,additional_kwargs={"complete": True})]}