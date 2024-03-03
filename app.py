import PyPDF2
import streamlit as st
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from htmlTemplates import css, bot_template, user_template
from langchain.llms import HuggingFaceHub
import time
from openai.error import RateLimitError



#progress bar for retry beacuse using free versions
#if we have premium version means we can ignore that these make_openai_request_with_progress(prompt)
def make_openai_request_with_progress(prompt):
    max_retries = 14  # Adjust the maximum number of retries as needed
    retry_delay = 30  # Seconds 

    for attempt in range(max_retries):
        try:
            response = st.session_state.conversation({'question': prompt})
            return response
        except RateLimitError as e:
            retry_message = st.warning(f"Rate limit reached. Retrying... (Attempt {attempt + 1}/{max_retries})")
            progress_bar = st.progress(0)
            for i in range(retry_delay):
                time.sleep(1)
                progress_bar.progress((i + 1) / retry_delay)
            retry_message.empty()
            progress_bar.empty()

    st.error(f"Failed after {max_retries} attempts. Rate limit still reached.")
    raise RateLimitError("Rate limit reached. Unable to make successful request.")


#extract text  from the pdfs
def get_pdf_text(pdf_docs, max_pages=None):
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        num_pages = len(pdf_reader.pages)

        if max_pages is not None:
            num_pages = min(num_pages, max_pages)

        for i, page in enumerate(pdf_reader.pages):
            if i >= num_pages:
                break
            text += page.extract_text()
    return text


#splitting text as chuncks
def get_text_chunks(text):
    print(text)
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks


#embedding and store in faiss
def get_vectorstore(text_chunks):
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
    return vectorstore


#make a conversation
def get_conversation_chain(vectorstore):
    llm = ChatOpenAI()
    memory = ConversationBufferMemory(
        memory_key='chat_history', return_messages=True)
    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        memory=memory
    )
    return conversation_chain


#handling our prompt input
def handle_userinput(user_question):
    try:
        response = make_openai_request_with_progress(user_question)
        st.session_state.chat_history = response['chat_history']

        for i, message in enumerate(st.session_state.chat_history):
            if i % 2 == 0:
                st.write(user_template.replace(
                    "{{MSG}}", message.content), unsafe_allow_html=True)
            else:
                st.write(bot_template.replace(
                    "{{MSG}}", message.content), unsafe_allow_html=True)

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")



def main():

    #load .env file for getting huggingface and openai access token key
    load_dotenv()

    #title icon of the page
    st.set_page_config(page_title="Chat with multiple PDFs",
                       page_icon=":books:")
    
    #import css style
    st.write(css, unsafe_allow_html=True)
     

    #check conversation still in or not
    if "conversation" not in st.session_state:
        st.session_state.conversation = None
    
    #title
    st.header("Chat with multiple PDFs :books:")

    #asking question-user propmts
    user_question = st.text_input("Ask a question about your documents:")

    #answer generrate for the prompt of call
    if user_question:
        handle_userinput(user_question)

    #nav sidev=bar
    with st.sidebar:
        st.subheader("Your documents")


        #upload multiple documenst
        pdf_docs = st.file_uploader(
            "Upload your PDFs here and click on 'Process'", accept_multiple_files=True)
        
        #to process multiple docs
        if st.button("Process"):
            with st.spinner("Processing"):
                
                # get limited pdf text because of free versions computation is high so need premium account
                raw_text = get_pdf_text(pdf_docs, max_pages=10)

                # get the text chunks
                text_chunks = get_text_chunks(raw_text)

                # create vector store to store a chunks embedded texts
                vectorstore = get_vectorstore(text_chunks)

                # create conversation chain and maintain 
                st.session_state.conversation = get_conversation_chain(
                    vectorstore)


#main loading
if __name__ == '__main__':
    main()
