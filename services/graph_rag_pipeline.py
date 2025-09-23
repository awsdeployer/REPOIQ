from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda
from langchain_core.prompts import PromptTemplate
from langchain_aws import ChatBedrock
from langchain_community.embeddings import BedrockEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
import tempfile, os, shutil, logging
from typing import Dict, Any

def build_graph_rag(docs, repo_id):
    MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    llm = ChatBedrock(model_id=MODEL_ID)
    embeddings = BedrockEmbeddings(model_id="amazon.titan-embed-text-v1")
    splitter = RecursiveCharacterTextSplitter(chunk_size=20000, chunk_overlap=200)
    qa_prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=(
            "You are an expert developer analyzing a GitHub repository.\n"
            "Use ONLY the repository context below to answer questions.\n"
            "Always cite the file name(s).\n\n"
            "Repository Context:\n{context}\n\n"
            "Question: {question}\n\n"
            "Answer clearly, and reference the file(s)."
        )
    )

    # State schema: a dict with keys for each step
    state_schema = Dict[str, Any]

    def split_node(state):
        docs = state["docs"]
        logging.info(f"LangGraph: split_node running for repo_id={repo_id}, num_docs={len(docs)}")
        splits = splitter.split_documents(docs)
        logging.info(f"LangGraph: split_node produced {len(splits)} splits")
        return {**state, "splits": splits}

    def embed_store_node(state):
        splits = state["splits"]
        logging.info(f"LangGraph: embed_store_node running for repo_id={repo_id}, num_splits={len(splits)}")
        index_path = os.path.join(tempfile.gettempdir(), f"faiss_index_{repo_id}")
        if os.path.exists(index_path):
            shutil.rmtree(index_path)
        vectorstore = FAISS.from_documents(splits, embeddings)
        vectorstore.save_local(index_path)
        logging.info(f"LangGraph: embed_store_node saved FAISS index at {index_path}")
        return {**state, "vectorstore": vectorstore}

    def retriever_node(state):
        logging.info(f"LangGraph: retriever_node running for repo_id={repo_id}")
        vectorstore = state["vectorstore"]
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
        logging.info(f"LangGraph: retriever_node created retriever")
        return {**state, "retriever": retriever}

    def qa_node(state):
        logging.info(f"LangGraph: qa_node running for repo_id={repo_id}")
        retriever = state["retriever"]
        qa = None  
        logging.info(f"LangGraph: qa_node completed")
        return {**state, "qa": qa}


    graph = StateGraph(state_schema)
    graph.add_node("split", RunnableLambda(split_node))
    graph.add_node("embed_store", RunnableLambda(embed_store_node))
    graph.add_node("retriever", RunnableLambda(retriever_node))
    graph.add_node("qa", RunnableLambda(qa_node))

    graph.add_edge("split", "embed_store")
    graph.add_edge("embed_store", "retriever")
    graph.add_edge("retriever", "qa")
    graph.add_edge("qa", END)

    graph.set_entry_point("split")
    return graph.compile()
