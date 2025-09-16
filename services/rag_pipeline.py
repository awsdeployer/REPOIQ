import os, shutil, tempfile, logging
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain_aws import ChatBedrock
from langchain_community.embeddings import BedrockEmbeddings

MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"
llm = ChatBedrock(model_id=MODEL_ID)
embeddings = BedrockEmbeddings(model_id="amazon.titan-embed-text-v1")

def build_rag(docs, repo_id):
    if not docs:
        raise ValueError("No text-extractable files found in the repository.")



    splitter = RecursiveCharacterTextSplitter(chunk_size=20000, chunk_overlap=200)
    splits = splitter.split_documents(docs)

    # Batch embedding: embed all splits at once
    texts = [doc.page_content for doc in splits]
    metadatas = [doc.metadata for doc in splits]
    vectors = embeddings.embed_documents(texts)

    # Use FAISS.from_embeddings for fast index creation
    from langchain_community.vectorstores.faiss import FAISS as FAISSClass
    vectorstore = FAISSClass.from_embeddings(vectors, texts, metadatas)

    index_path = os.path.join(tempfile.gettempdir(), f"faiss_index_{repo_id}")
    if os.path.exists(index_path):
        shutil.rmtree(index_path)
    vectorstore.save_local(index_path)

    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

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

    qa = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        chain_type_kwargs={"prompt": qa_prompt}
    )

    return qa, vectorstore, retriever

