import os
from functools import partial
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from node import detect_qtype, search_vector_db, terminate, search_llm
from utils import State
from langgraph.graph import MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.docstore.in_memory import InMemoryDocstore
from utils import State, get_all_urls
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
import faiss

embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
index = faiss.IndexFlatL2(len(embeddings.embed_query("aposit")))

vector_store = FAISS(
    embedding_function=embeddings,
    index=index,
    docstore=InMemoryDocstore(),
    index_to_docstore_id={}
)

def collect_webcontents():
    if not os.path.exists("faiss_index"):
        urls = get_all_urls("https://www.aposto.it")
        loader = WebBaseLoader(
            web_paths=urls
        )
        docs = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        all_splits = text_splitter.split_documents(docs)
        vector_store = FAISS.from_documents(all_splits, embeddings)
        vector_store.save_local("faiss_index")
        
collect_webcontents()

llm = ChatOpenAI(model="gpt-4o", temperature=0)
memory = MemorySaver()

def decide_route(state) -> Literal["search_llm", "terminate"]:
    relevant = state['relevant']
    if relevant=="yes":
        return "search_llm"
    else:
        return "terminate"

# Build graph
builder = StateGraph(State)
builder.add_node("detect_qtype", partial(detect_qtype, llm=llm))
builder.add_node("search_vector_db", partial(search_vector_db, llm=llm, embeddings=embeddings))
builder.add_node("search_llm", partial(search_llm, llm=llm))
builder.add_node("terminate", partial(terminate, llm=llm))

builder.add_edge(START, "detect_qtype")
builder.add_conditional_edges("detect_qtype", decide_route)
builder.add_edge("terminate", END)
builder.add_edge("search_llm", "search_vector_db")
builder.add_edge("search_vector_db", END)

# Compile graph
graph = builder.compile(checkpointer=memory)

