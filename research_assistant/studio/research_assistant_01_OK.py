from dotenv import load_dotenv
load_dotenv()

import os
import operator
from pydantic import BaseModel, Field
from typing import Annotated, List
from typing_extensions import TypedDict

from reportlab.pdfgen import canvas

from langchain_community.document_loaders import WikipediaLoader
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, get_buffer_string
from langchain_openai import ChatOpenAI

from langgraph.constants import Send
from langgraph.graph import END, MessagesState, START, StateGraph

openai_api_key = os.getenv("OPENAI_API_KEY")
tavily_api_key = os.getenv("TAVILY_API_KEY")
langsmith_api_key = os.getenv("TAVILY_API_KEY")


if not openai_api_key or not tavily_api_key:
    raise EnvironmentError("API keys are not set. Check your .env file.")

### LLM

llm = ChatOpenAI(model="gpt-4o", temperature=0)
#llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
#llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
#llm = ChatOpenAI(model="gpt-4-turbo", temperature=0)

### Schema 

class Analyst(BaseModel):
    name: str = Field(
        description="Name of the analyst. Only use Italian names"
    )
    affiliation: str = Field(
        description="Primary affiliation of the analyst.",
    )
    role: str = Field(
        description="Role of the analyst in the context of the topic.",
    )
    description: str = Field(
        description="Description of the analyst focus, concerns, and motives.",
    )
    @property
    def persona(self) -> str:
        return f"Name: {self.name}\nRole: {self.role}\nAffiliation: {self.affiliation}\nDescription: {self.description}\n"

class Perspectives(BaseModel):
    analysts: List[Analyst] = Field(
        description="Comprehensive list of analysts with their roles and affiliations.",
    )

class GenerateAnalystsState(TypedDict):
    topic: str  # Research topic
    max_analysts: int  # Number of analysts
    human_analyst_feedback: str  # Human feedback
    analysts: List[Analyst]  # Analyst asking questions

class InterviewState(MessagesState):
    max_num_turns: int  # Number turns of conversation
    context: Annotated[list, operator.add]  # Source docs
    analyst: Analyst  # Analyst asking questions
    interview: str  # Interview transcript
    sections: list  # Final key we duplicate in outer state for Send() API

class SearchQuery(BaseModel):
    search_query: str = Field(None, description="Search query for retrieval.")

class ResearchGraphState(TypedDict):
    topic: str  # Research topic
    max_analysts: int  # Number of analysts
    human_analyst_feedback: str  # Human feedback
    analysts: List[Analyst]  # Analyst asking questions
    sections: Annotated[list, operator.add]  # Send() API key
    introduction: str  # Introduction for the final report
    content: str  # Content for the final report
    conclusion: str  # Conclusion for the final report
    final_report: str  # Final report


### Interrupt Configuration

# You can enable or disable interrupt-before for the main graph nodes here
INTERRUPT_CONFIG_MAIN = {
    "human_feedback": False,    # Interrupt before node 'human_feedback'
    "write_report": False,    # Interrupt before node 'human_feedback'
}

# You can enable or disable interrupt-before for the nested interview graph nodes here
INTERRUPT_CONFIG_INTERVIEW = {
    "search_web": False,        # Interrupt before node 'search_web'
    "search_wikipedia": False,
    "answer_question": False,
    "save_interview": False,
    "write_section": False,

}

def get_enabled_interrupts(config: dict) -> list:
    """Returns a list of node names for which interrupts are enabled."""
    return [node for node, enabled in config.items() if enabled]


### Nodes and edges

analyst_instructions = """
Tutte le interazioni devono essere in italiano!!
You are an analyst 
You are tasked with creating a set of AI analyst personas. 
Each analyst will be tasked with interviewing an expert to learn about a specific topic.
Follow these instructions carefully:
1. First, review the research topic:
{topic} 
2. Examine any editorial feedback that has been optionally provided, to guide creation of the analysts: 
{human_analyst_feedback}
3. You will find in the prompt some numbered areas
For example:
AREE:
1) Theme 1
2) Theme 2
3) Theme 3
And so on....
Pick the numbered areas from the prompt and use them as themes
You will use these themes later on, to craft your report.
4. Pick the top {max_analysts} themes.
5. Assign one analyst to each theme.
"""

def create_analysts(state: GenerateAnalystsState):
    """ Create analysts """

    # Ensure all interactions are in Italian
    italian_prompt = SystemMessage(content="Tutte le interazioni devono essere in italiano.")
    state['messages'] = [italian_prompt] + state.get('messages', [])
    
    topic = state['topic']
    max_analysts = state['max_analysts']
    human_analyst_feedback = state.get('human_analyst_feedback', '')

    # Enforce structured output
    structured_llm = llm.with_structured_output(Perspectives)

    # System message
    system_message = analyst_instructions.format(
        topic=topic,
        human_analyst_feedback=human_analyst_feedback, 
        max_analysts=max_analysts
    )

    # Generate analysts
    analysts = structured_llm.invoke(
        [SystemMessage(content=system_message)] 
        + [HumanMessage(content="Generate the set of analysts.")]
    )

    # Write the list of analysts to state
    return {"analysts": analysts.analysts}


def human_feedback(state: GenerateAnalystsState):
    """ No-op node that should be interrupted on """
    pass


# Generate analyst question
question_instructions = """
Tutte le interazioni devono essere in italiano!!
You are an analyst tasked with interviewing an expert to learn about a specific topic. 

You will find areas in the topic, always in this format:
1)
2)
3)
....

ONLY CREATE QUESTIONS THAT ARE RELATED TO THE AREAS THAT BEST MATCHES YOUR ANALYST ROLE
MAKE SURE YOU DON'T ASK QUESTIONS ABOUT AREAS THAT ARE NOT RELATED TO YOUR ROLE
Your questions should always be:
1. Interesting: Insights that people will find surprising or non-obvious.      
2. Specific: Insights that avoid generalities and include specific examples from the expert.

You will find objectives in the topic, always in this format:
QUE_OBJ: “ “
Your questions should be crafted strictly following the objective

Here is your topic. Remember to concentrate on the areas you find in it: {goals}
        
Begin by introducing yourself using a name that fits your persona, and then ask your question.
Continue to ask questions to drill down and refine your understanding of the topic.
When you are satisfied with your understanding, complete the interview with: "Thank you so much for your help!"
Pay particular attention to the objective
"""

def generate_question(state: InterviewState):
    """ Node to generate a question """

    analyst = state["analyst"]
    messages = state["messages"]

    # Generate question 
    system_message = question_instructions.format(goals=analyst.persona)
    question = llm.invoke([SystemMessage(content=system_message)] + messages)
        
    # Write messages to state
    return {"messages": [question]}


# Search query writing
search_instructions = SystemMessage(content=f"""
You will be given a conversation between an analyst and an expert. 

Your goal is to generate a well-structured query for use in retrieval and / or web-search related to the conversation and the context.
        
First, analyze the full conversation and the whole context at your disposal.

Remember that the query must always be relevant to the analyst role and his area of interest. When you build your query, do not include the other areas. Only the one that is coherent with the analyst role that you find in the context.
YOUR QUERY MUST BE FOCUSED ON THE ANALYST ROLE AND THE RESPECTIVE AREA
Also, concentrate on the objective you find in the context, always recognizable in the QUE_OBJ line                                                    

Produce a well-structured web search query
""")

def search_web(state: InterviewState):
    """ Retrieve docs from web search """

    tavily_search = TavilySearchResults(max_results=3)

    # Search query
    structured_llm = llm.with_structured_output(SearchQuery)
    search_query = structured_llm.invoke([search_instructions] + state['messages'])
    
    # Search
    search_docs = tavily_search.invoke(search_query.search_query)

    # Format
    formatted_search_docs = "\n\n---\n\n".join(
        [
            f'<Document href="{doc["url"]}"/>\n{doc["content"]}\n</Document>'
            for doc in search_docs
        ]
    )

    return {"context": [formatted_search_docs]} 


def search_wikipedia(state: InterviewState):
    """ Retrieve docs from wikipedia """

    # Search query
    structured_llm = llm.with_structured_output(SearchQuery)
    search_query = structured_llm.invoke([search_instructions] + state['messages'])
    
    # Search
    search_docs = WikipediaLoader(query=search_query.search_query, load_max_docs=2).load()

    # Format
    formatted_search_docs = "\n\n---\n\n".join(
        [
            f'<Document source="{doc.metadata["source"]}" page="{doc.metadata.get("page", "")}"/>\n{doc.page_content}\n</Document>'
            for doc in search_docs
        ]
    )

    return {"context": [formatted_search_docs]} 


# Generate expert answer
answer_instructions = """Tutte le interazioni devono essere in italiano!!
You are an expert being interviewed by an analyst.

Here is analyst area of focus: {goals}. 
        
You goal is to answer a question posed by the interviewer.

To answer question, use this context:
        
{context}

When answering questions, follow these guidelines:
        
1. Use only the information provided in the context. 
        
2. Do not introduce external information or make assumptions beyond what is explicitly stated in the context.

3. The context contain sources at the topic of each individual document.

4. Include these sources your answer next to any relevant statements. For example, for source # 1 use [1]. 

5. List your sources in order at the bottom of your answer. [1] Source 1, [2] Source 2, etc
        
6. If the source is: <Document source="assistant/docs/llama3_1.pdf" page="7"/>' then just list: 
        
[1] assistant/docs/llama3_1.pdf, page 7 
        
And skip the addition of the brackets as well as the Document source preamble in your citation."""

def generate_answer(state: InterviewState):
    """ Node to answer a question """

    analyst = state["analyst"]
    messages = state["messages"]
    context = state["context"]

    # Answer question
    system_message = answer_instructions.format(goals=analyst.persona, context=context)
    answer = llm.invoke([SystemMessage(content=system_message)] + messages)
            
    # Name the message as coming from the expert
    answer.name = "expert"
    
    # Append it to state
    return {"messages": [answer]}


def save_interview(state: InterviewState):
    """ Save interviews """

    messages = state["messages"]
    # Convert interview to a string
    interview = get_buffer_string(messages)
    # Save to interviews key
    return {"interview": interview}


def route_messages(state: InterviewState, name: str = "expert"):
    """ Route between question and answer """
    
    messages = state["messages"]
    max_num_turns = state.get('max_num_turns', 2)

    # Check the number of expert answers 
    num_responses = len(
        [m for m in messages if isinstance(m, AIMessage) and m.name == name]
    )

    # End if expert has answered more than the max turns
    if num_responses >= max_num_turns:
        return 'save_interview'

    # This router is run after each question - answer pair 
    # Get the last question asked to check if it signals the end of discussion
    last_question = messages[-2]
    
    if "Thank you so much for your help" in last_question.content:
        return 'save_interview'
    return "ask_question"


# Write a summary (section of the final report) of the interview
section_writer_instructions = """
Tutte le interazioni devono essere in italiano!!
You are an expert technical writer. 



Your task is to create a short, easily digestible section of a report based on a set of source documents.


1. Analyze the content of the source documents: 
- Analyze the content of the original topic provided and structure your report to answer the questions you find in the topic
- The name of each source document is at the start of the document, with the <Document tag.

2. Write the report following this structure:
a. Title (@ header)
b. The results of instructions in the SEC_OBJ, in the topic
c. Details for each @@ header
d. Sources (@@@ header)

4. Make your title engaging based upon the focus area of the analyst: 
{focus}

5. For the details section:
- Always structure the Survey to be relevant to the original topic submitted at the start
- Set up summary with general background / context related to the focus area of the analyst
- Emphasize what is novel, interesting, or surprising about insights gathered from the interview
- Create a numbered list of source documents, as you use them
- Do not mention the names of interviewers or experts
- Aim for approximately 400 words maximum
- Use numbered sources in your report (e.g., [1], [2]) based on information from source documents
        
6. In the Sources section:
- Include all sources used in your report
- Provide full links to relevant websites or specific document paths
- Separate each source by a newline. Use two spaces at the end of each line to create a newline in Markdown.
- It will look like:

### Sources
[1] Link or Document name
[2] Link or Document name

7. Be sure to combine sources. For example this is not correct:

[3] https://ai.meta.com/blog/meta-llama-3-1/
[4] https://ai.meta.com/blog/meta-llama-3-1/

There should be no redundant sources. It should simply be:

[3] https://ai.meta.com/blog/meta-llama-3-1/
        
8. Final review:
- Ensure the report follows the required structure
- Include no preamble before the title of the report
- Check that all guidelines have been followed
"""

def write_section(state: InterviewState):
    """ Node to write a section """

    interview = state["interview"]
    context = state["context"]
    analyst = state["analyst"]
   
    # Write section using either the gathered source docs from interview (context) or the interview itself
    system_message = section_writer_instructions.format(focus=analyst.description)
    section = llm.invoke(
        [
            SystemMessage(content=system_message)
        ] + [
            HumanMessage(content=f"Use this source to write your section: {context}")
        ]
    ) 
                
    # Append it to state
    return {"sections": [section.content]}


# Build the interview sub-graph
interview_builder = StateGraph(InterviewState)
interview_builder.add_node("ask_question", generate_question)
interview_builder.add_node("search_web", search_web)
interview_builder.add_node("search_wikipedia", search_wikipedia)
interview_builder.add_node("answer_question", generate_answer)
interview_builder.add_node("save_interview", save_interview)
interview_builder.add_node("write_section", write_section)

# Flow
interview_builder.add_edge(START, "ask_question")
interview_builder.add_edge("ask_question", "search_web")
interview_builder.add_edge("ask_question", "search_wikipedia")
interview_builder.add_edge("search_web", "answer_question")
interview_builder.add_edge("search_wikipedia", "answer_question")
interview_builder.add_conditional_edges("answer_question", route_messages, ["ask_question", "save_interview"])
interview_builder.add_edge("save_interview", "write_section")
interview_builder.add_edge("write_section", END)

# Compile the interview sub-graph with dynamic interrupt list
interview_interrupt_nodes = get_enabled_interrupts(INTERRUPT_CONFIG_INTERVIEW)
interview_graph = interview_builder.compile(interrupt_before=interview_interrupt_nodes)


def initiate_all_interviews(state: ResearchGraphState):
    """ Conditional edge to initiate all interviews via Send() API or return to create_analysts """    

    human_analyst_feedback = state.get('human_analyst_feedback','approve').lower()
    if human_analyst_feedback != 'approve':
        # Return to create_analysts
        return "create_analysts"
    else:
        # Otherwise kick off interviews in parallel via Send() API
        topic = state["topic"]
        return [
            Send(
                "conduct_interview",
                {
                    "analyst": analyst,
                    "messages": [
                        HumanMessage(content=f"Vorrei informazioni dettagliate su {topic}?")
                    ]
                }
            ) 
            for analyst in state["analysts"]
        ]


# Write a report based on the interviews
report_writer_instructions = """Tutte le interazioni devono essere in italiano!!
You are a technical writer creating a report on this overall topic: 

{topic}
    
You have a team of analysts. Each analyst has done two things: 

1. They conducted an interview with an expert on a specific sub-topic.
2. They write up their finding into a memo.

Your task: 

1. You will be given a collection of memos from your analysts.
2. Think carefully about the insights from each memo.
3. Consolidate these into a crisp overall summary that ties together the central ideas from all of the memos. 
4. Summarize the central points in each memo into a cohesive single narrative.

To format your report:
 
1. Use markdown formatting. 
2. Include no pre-amble for the report.
3. Use no sub-heading. 
4. Start your report with a single title header: ## Insights
5. Do not mention any analyst names in your report.
6. Preserve any citations in the memos, which will be annotated in brackets, for example [1] or [2].
7. Create a final, consolidated list of sources and add to a Sources section with the `## Sources` header.
8. List your sources in order and do not repeat.

[1] Source 1
[2] Source 2

Here are the memos from your analysts to build your report from: 

{context}"""

def write_report(state: ResearchGraphState):
    """ Node to write the final report body """

    sections = state["sections"]
    topic = state["topic"]

    # Concat all sections together
    formatted_str_sections = "\n\n".join([f"{section}" for section in sections])
    
    # Summarize the sections into a final report
    system_message = report_writer_instructions.format(topic=topic, context=formatted_str_sections)
    report = llm.invoke(
        [
            SystemMessage(content=system_message)
        ] + [
            HumanMessage(content=f"Write a report based upon these memos.")
        ]
    ) 
    return {"content": report.content}


# Write the introduction or conclusion
intro_conclusion_instructions = """Tutte le interazioni devono essere in italiano!!
You are a technical writer finishing a report on {topic}

You will be given all of the sections of the report.

You job is to write a crisp and compelling introduction or conclusion section.

The user will instruct you whether to write the introduction or conclusion.

Include no pre-amble for either section.

Target around 100 words, crisply previewing (for introduction) or recapping (for conclusion) all of the sections of the report.

Use markdown formatting. 

For your introduction, create a compelling title and use the # header for the title.

For your introduction, use ## Introduction as the section header. 

For your conclusion, use ## Conclusion as the section header.

Here are the sections to reflect on for writing: {formatted_str_sections}"""

def write_introduction(state: ResearchGraphState):
    """ Node to write the introduction """

    sections = state["sections"]
    topic = state["topic"]

    formatted_str_sections = "\n\n".join([f"{section}" for section in sections])
    
    instructions = intro_conclusion_instructions.format(topic=topic, formatted_str_sections=formatted_str_sections)
    intro = llm.invoke([instructions] + [HumanMessage(content=f"Write the report introduction")])
    return {"introduction": intro.content}


def write_conclusion(state: ResearchGraphState):
    """ Node to write the conclusion """

    sections = state["sections"]
    topic = state["topic"]

    formatted_str_sections = "\n\n".join([f"{section}" for section in sections])
    
    instructions = intro_conclusion_instructions.format(topic=topic, formatted_str_sections=formatted_str_sections)
    conclusion = llm.invoke([instructions] + [HumanMessage(content=f"Write the report conclusion")])
    return {"conclusion": conclusion.content}


def finalize_report(state: ResearchGraphState):
    """The 'reduce' step where we combine all sections, write intro/conclusion, and export as PDF."""

    # Log file path
    log_dir = "/Users/pierobiggi/AI_gitlab/langgraph/research_Assistant/reports/"
    log_file_path = os.path.join(log_dir, "debug_log.txt")
    
    # Ensure the directory for logs exists
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception as e:
        print(f"Error creating log directory: {e}")
        return {"error": "Failed to create log directory"}
    
    # Function to log messages
    def log_message(message):
        with open(log_file_path, "a") as log_file:
            log_file.write(message + "\n")

    # Save full final report
    content = state["content"]
    if content.startswith("## Insights"):
        content = content.strip("## Insights")
    if "## Sources" in content:
        try:
            content, sources = content.split("\n## Sources\n")
        except Exception as e:
            log_message(f"Error splitting content and sources: {e}")
            sources = None
    else:
        sources = None

    final_report = state["introduction"] + "\n\n---\n\n" + content + "\n\n---\n\n" + state["conclusion"]
    if sources is not None:
        final_report += "\n\n## Sources\n" + sources

    # Save final report in state
    state["final_report"] = final_report

    # Debug log of the final report content
    log_message("Final report content:")
    log_message(final_report)
    
    # Ensure directory exists for the PDF
    pdf_dir = "/Users/pierobiggi/AI_gitlab/langgraph/research_Assistant/reports/"
    log_message(f"Ensuring the directory exists: {pdf_dir}")
    try:
        os.makedirs(pdf_dir, exist_ok=True)  # Create the directory if it doesn't exist
    except Exception as e:
        log_message(f"Error creating directory: {e}")
        return {"error": "Failed to create directory"}

    pdf_path = os.path.join(pdf_dir, "final_report_reportlab.pdf")
    log_message(f"Attempting to save PDF to: {pdf_path}")

    try:
        # Create PDF with ReportLab
        c = canvas.Canvas(pdf_path, pagesize=(595.27, 841.89))  # A4 size
        c.setFont("Helvetica", 12)

        # Debug log of PDF generation process
        log_message("Starting PDF generation...")

        # Add content line by line with word wrapping
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.utils import simpleSplit

        page_width, page_height = letter
        margin = 50
        max_width = page_width - 2 * margin
        y_position = page_height - margin  # Start at the top of the page
        line_height = 14  # Space between lines

        for line in final_report.split("\n"):
            wrapped_lines = simpleSplit(line, c._fontname, c._fontsize, max_width)
            for wrapped_line in wrapped_lines:
                if y_position <= margin:  # Start a new page if we run out of space
                    log_message("Adding a new page...")
                    c.showPage()
                    c.setFont("Helvetica", 12)
                    y_position = page_height - margin
                c.drawString(margin, y_position, wrapped_line)
                y_position -= line_height
        
        c.save()  # Save the PDF
        log_message(f"PDF successfully saved to: {pdf_path}")
    except Exception as e:
        log_message(f"An error occurred while saving the PDF: {e}")
        return {"error": "PDF generation failed"}

    # Verify if the PDF file actually exists
    if os.path.exists(pdf_path):
        log_message(f"PDF verified at: {pdf_path}")
    else:
        log_message(f"PDF not found at expected location: {pdf_path}")
        return {"error": "PDF file missing after save attempt"}

    state["pdf_path"] = pdf_path  # Save the PDF path in state
    return {"final_report": final_report, "pdf_path": pdf_path}


### Build the main graph
builder = StateGraph(ResearchGraphState)
builder.add_node("create_analysts", create_analysts)
builder.add_node("human_feedback", human_feedback)
builder.add_node("conduct_interview", interview_graph)  # nested interview
builder.add_node("write_report", write_report)
builder.add_node("write_introduction", write_introduction)
builder.add_node("write_conclusion", write_conclusion)
builder.add_node("finalize_report", finalize_report)

# Logic
builder.add_edge(START, "create_analysts")
builder.add_edge("create_analysts", "human_feedback")
builder.add_conditional_edges("human_feedback", initiate_all_interviews, ["create_analysts", "conduct_interview"])
builder.add_edge("conduct_interview", "write_report")
builder.add_edge("conduct_interview", "write_introduction")
builder.add_edge("conduct_interview", "write_conclusion")
builder.add_edge(["write_conclusion", "write_report", "write_introduction"], "finalize_report")
builder.add_edge("finalize_report", END)

# Compile the main graph with dynamic interrupt list
main_interrupt_nodes = get_enabled_interrupts(INTERRUPT_CONFIG_MAIN)
graph = builder.compile(interrupt_before=main_interrupt_nodes)
