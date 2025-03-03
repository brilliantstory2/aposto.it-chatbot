import os
from functools import partial
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from node import detect_qtype, find_link, terminate, search_llm, promotion, workshop
from utils import State
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.docstore.in_memory import InMemoryDocstore
from utils import State, getPagesFromSitemap
from langchain_community.vectorstores import FAISS
import faiss
# import multiprocessing
# from apscheduler.schedulers.background import BackgroundScheduler
import time

embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
index = faiss.IndexFlatL2(len(embeddings.embed_query("aposto")))
faiss_db = os.environ["FAISS_VECTOR_DB"]

vector_store = FAISS(
    embedding_function=embeddings,
    index=index,
    docstore=InMemoryDocstore(),
    index_to_docstore_id={}
)

def collect_webcontents():
    if not os.path.exists(faiss_db):
        urls = getPagesFromSitemap("https://www.aposto.it")
        loader = WebBaseLoader(
            web_paths=urls
        )
        docs = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        all_splits = text_splitter.split_documents(docs)
        vector_store = FAISS.from_documents(all_splits, embeddings)
        vector_store.save_local(faiss_db)
        
collect_webcontents()


llm = ChatOpenAI(model="gpt-4o", temperature=0)
memory = MemorySaver()

def decide_route(state) -> Literal["search_llm","promotion","workshop", "terminate"]:
    relevant = state['relevant']
    if relevant=="llm":
        return "search_llm"
    elif relevant=="promotion":
        return "promotion"
    elif relevant=="workshop":
        return "workshop"
    else:
        return "terminate"

# Build graph
builder = StateGraph(State)
builder.add_node("detect_qtype", partial(detect_qtype, llm=llm))
builder.add_node("find_link", partial(find_link, llm=llm, embeddings=embeddings))
builder.add_node("search_llm", partial(search_llm, llm=llm))
builder.add_node("terminate", partial(terminate, llm=llm))
builder.add_node("workshop", partial(workshop, llm=llm))
builder.add_node("promotion",  partial(promotion, llm=llm, embeddings=embeddings))

builder.add_edge(START, "detect_qtype")
builder.add_conditional_edges("detect_qtype", decide_route)
builder.add_edge("terminate", END)
builder.add_edge("search_llm", "find_link")
builder.add_edge("find_link", END)
builder.add_edge("promotion", END)
builder.add_edge("workshop", END)

# Compile graph
graph = builder.compile(checkpointer=memory)

# def start_scheduler():
#     scheduler = BackgroundScheduler()
#     scheduler.add_job(update_vector_db, 'cron', hour=8, minute=0)  # Runs at 8:00 AM daily
#     scheduler.start()

#     try:
#         while True:
#             time.sleep(1)  # Keep the process running
#     except KeyboardInterrupt:
#         scheduler.shutdown()

# scheduler_process = multiprocessing.Process(target=start_scheduler)
# scheduler_process.start()






