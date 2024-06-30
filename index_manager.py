from llama_index import (
    VectorStoreIndex,
    StorageContext,
    ServiceContext,
    LLMPredictor,
)
import torch
from transformers import BitsAndBytesConfig
from llama_index.prompts import PromptTemplate
from llama_index.llms import HuggingFaceLLM


from llama_index.indices.loading import load_index_from_storage
from utils.vector_database import build_pinecone_vector_store, build_mongo_index
from mongodb.index import getExistingLlamaIndexes
from llama_index import SimpleDirectoryReader

from llama_index.llms import Perplexity
import os


quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
)



llm = HuggingFaceLLM(
    model_name="mistralai/Mistral-7B-Instruct-v0.1",
    tokenizer_name="mistralai/Mistral-7B-Instruct-v0.1",
    query_wrapper_prompt=PromptTemplate("<s>[INST] {query_str} [/INST] </s>\n"),
    context_window=3900,
    max_new_tokens=256,
    model_kwargs={"quantization_config": quantization_config},
    # tokenizer_kwargs={},
    generate_kwargs={"temperature": 0.2, "top_k": 5, "top_p": 0.95},
    device_map="auto",
)

index_store = build_mongo_index()
vector_store = build_pinecone_vector_store()

llm_predictor = LLMPredictor(llm=llm)

service_context = ServiceContext.from_defaults(
    llm_predictor=llm_predictor,
    embed_model="local:BAAI/bge-small-en-v1.5",
)

storage_context = StorageContext.from_defaults(
    index_store=index_store,
    vector_store=vector_store
)

mongoIndex = None


def initialize_index():
    existing_indexes = getExistingLlamaIndexes()

    global mongoIndex

    if len(existing_indexes) > 0:
        print("Loading existing index...")

        mongoIndex = load_index_from_storage(
            service_context=service_context,
            storage_context=storage_context,
            llm_predictor=llm_predictor,
            index_id='mongo-index',
        )

        return createQueryEngine(mongoIndex)
    else:
        print("Building index...")

        mongoIndex = buildVectorIndex()

        return createQueryEngine(mongoIndex)


def createQueryEngine(index):
    return index.as_query_engine(response_mode="simple_summarize", top_k=3)


def get_service_context():
    return service_context


def buildVectorIndex():
    reader = SimpleDirectoryReader(
        input_files=["./data/rules.pdf"]
    )
    
    documents = reader.load_data()

    index = VectorStoreIndex.from_documents(
        documents,
        service_context=service_context,
        storage_context=storage_context
    )

    index.set_index_id("mongo-index")

    return index