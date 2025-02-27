import openai
from django.conf import settings
from langchain import LLMChain, PromptTemplate
from langchain.callbacks.manager import AsyncCallbackManager
from langchain.chat_models import ChatOpenAI
from langchain.llms import AzureOpenAI
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain.schema import SystemMessage

from ayushma.models.enums import ModelType
from ayushma.utils.stream_callback import StreamingQueueCallbackHandler
from core.settings.base import AI_NAME


def get_model_name(model_type: ModelType):
    if model_type == ModelType.GPT_3_5:
        if settings.OPENAI_API_TYPE == "azure":
            return "gpt-35-turbo"
        return "gpt-3.5-turbo"
    elif model_type == ModelType.GPT_3_5_16K:
        if settings.OPENAI_API_TYPE == "azure":
            return "gpt-35-turbo-16k"
        return "gpt-3.5-16k"
    elif model_type == ModelType.GPT_4:
        return "gpt-4"
    elif model_type == ModelType.GPT_4_32K:
        return "gpt-4-32k"
    else:
        if settings.OPENAI_API_TYPE == "azure":
            return settings.AZURE_CHAT_MODEL
        return "gpt-3.5-turbo"


class LangChainHelper:
    def __init__(
        self,
        openai_api_key=settings.OPENAI_API_KEY,
        model=ModelType.GPT_3_5,
        prompt_template=None,
        temperature=0.1,
        stream=True,
        token_queue=None,
        end=None,
        error=None,
    ):
        llm_args = {
            "temperature": temperature,  # 0 means more deterministic output, 1 means more random output
            "openai_api_key": openai_api_key,
            "model_name": get_model_name(model),
            "request_timeout": 180,
        }
        if stream:
            llm_args["streaming"] = True
            llm_args["callback_manager"] = AsyncCallbackManager(
                [StreamingQueueCallbackHandler(token_queue, end, error)]
            )

        if settings.OPENAI_API_TYPE == "azure":
            llm_args["deployment_name"] = settings.AZURE_CHAT_DEPLOYMENT
            llm_args["openai_api_version"] = openai.api_version
            llm = AzureOpenAI(**llm_args)
        else:
            llm = ChatOpenAI(**llm_args)

        template = f"""You are a female assistant called {AI_NAME} who understands all languages and repsonds only in english and you must follow the given algorithm strictly to assist users. Remember you must give accurate answers, so stick strictly to the references as explained in algorithm. Your output must be in markdown format find important terms and add bold to it (example **word**) find numbers and add italic to it(example *word*) add bullet points to a list(example -word1\n-word2):
Algorithm:
references = {{reference}}
/*
The references a dictionary with the key, value pairs in the following format:
<reference_id>: <text>
'text' is the content of the reference from what you can extract the information to solve the user's query.
*/

can_query_be_solved_by_given_references = <analyze the given "references" and current user's query and return true if "references" strictly contains the information to solve the current query else return false>
if "can_query_be_solved_by_given_references":
(
use_your_knowledge = <analyze "chat history with user" and "query" and generate an approriate result for the "query">
result = <analyze "references", chat history with user and user's current query to give the most descriptive and most accurate answer to solve the user's query related to medical emergencies.>
)
else:
(
result = <"Sorry I am not able to find anything related to your query in my database">

Output Format (follow the below format strictly and you must provide the references ids array in all your responses after the result. Do not mention about the references anywhere else):
'''
{AI_NAME}: <enter_result_here>
References: <array of reference_ids (in the format: [1,2,3]) "include all the reference ids in this array that are relevant and from which you formed the result">
'''"""
        if prompt_template:
            template = prompt_template

        if "{reference}" not in template:
            raise Exception(
                "Validation Error: Prompt template must contain {reference} variable"
            )

        system_prompt = PromptTemplate(template=template, input_variables=["reference"])
        system_message_prompt = SystemMessagePromptTemplate(
            prompt=system_prompt,
        )

        human_prompt = PromptTemplate(
            template="{user_msg}", input_variables=["user_msg"]
        )
        human_message_prompt = HumanMessagePromptTemplate(
            prompt=human_prompt,
        )

        message_prompt = MessagesPlaceholder(variable_name="chat_history")

        chat_prompt = ChatPromptTemplate.from_messages(
            [
                system_message_prompt,
                message_prompt,
                human_message_prompt,
            ]
        )

        self.chain = LLMChain(llm=llm, prompt=chat_prompt, verbose=True)

    async def get_aresponse(
        self, job_done, error, token_queue, user_msg, reference, chat_history
    ):
        chat_history.append(
            SystemMessage(
                content="remeber only answer the question if it can be answered with the given references"
            )
        )
        try:
            async_response = await self.chain.apredict(
                user_msg=f"user: {user_msg}",
                reference=reference,
                chat_history=chat_history,
            )
            token_queue.put((job_done,))
            return async_response
        except Exception as e:
            print(e)
            token_queue.put((error, e))

    def get_response(self, user_msg, reference, chat_history):
        chat_history.append(
            SystemMessage(
                content="remeber only answer the question if it can be answered with the given references"
            )
        )
        return self.chain.predict(
            user_msg=f"user: {user_msg}",
            reference=reference,
            chat_history=chat_history,
        )
