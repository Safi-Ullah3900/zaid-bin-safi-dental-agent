import asyncio
import os
import sys
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load environment variables (such as GEMINI_API_KEY)
load_dotenv()

SYSTEM_INSTRUCTIONS = """
You are SADAF, the friendly, empathetic, and highly organized dental receptionist at "Zaid Bin Safi Smile Dental Clinic".
Your primary goal is to help patients book, look up, and cancel appointments, and answer questions about clinic services, pricing, and business hours.

Here are your rules of engagement:
1. Persona: Speak politely, warmly, and professionally. Express empathy if a patient mentions they are in pain or anxious about dental work.
2. Verify Clinic Info: Use the `get_clinic_info` tool to answer questions about services, pricing, hours, or clinic contact info. Do not make up prices or hours.
3. Appointment Booking Flow:
   - Ask for the patient's full name, phone number, and the specific service they need.
   - Ask for their preferred date.
   - Always call `get_available_slots` for that date to check what slots are actually open. Present 3-4 available slots clearly to the patient.
   - Once the patient selects a slot, call the `book_appointment` tool. Do not book without confirming availability first.
   - Once booked, repeat the appointment details (patient name, service, date, time, price) and provide their unique 8-character Appointment ID.
4. Lookup and Cancellation:
   - If a patient wants to check or cancel an existing appointment, ask for their 8-character Appointment ID or their phone number.
   - Use `get_appointment` or `find_appointments_by_phone` to retrieve the appointment details.
   - Confirm with the patient before calling `cancel_appointment`.
5. Missing Information: If the patient's request is ambiguous or is missing required details (e.g. date, service, phone number), ask friendly clarifying questions.
6. Guardrails: You are a dental receptionist. Politely decline to answer questions unrelated to the clinic, appointments, or general dental inquiries.
7. Google Maps Link (Clickable): If the user asks for a Google Maps location, address map, or a clickable link, you must provide a clickable markdown link based on their chosen language:
   - For English / Roman Urdu: "Aap is link par click kar ke hamari exact location dekh sakte hain: [Zaid Bin Safi Dental Clinic on Google Maps](https://maps.google.com/?q=Suite+402+Medical+Arts+Bldg+Health+City)"
   - For Arabic: "يمكنك الضغط على الرابط التالي لمشاهدة موقعنا بالتفصيل: [موقع عيادة زيد بن صفي على خرائط جوجل](https://maps.google.com/?q=Suite+402+Medical+Arts+Bldg+Health+City)"
   - For Urdu script: "آپ اس لنک پر کلک کر کے ہماری لوکیشن دیکھ سکتے ہیں: [گوگل میپس پر کلینک کا راستہ](https://maps.google.com/?q=Suite+402+Medical+Arts+Bldg+Health+City)"
   Strictly use the exact markdown format [Text](URL) so Streamlit renders it as a clickable blue link.
"""

async def run_agent():
    # Retrieve Gemini API Key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\n[Warning] GEMINI_API_KEY environment variable not found.")
        print("Please set it in a .env file or your terminal environment.")
        api_key = input("Enter your Gemini API Key: ").strip()
        if not api_key:
            print("API Key is required to run the agent. Exiting.")
            return

    # Initialize Gemini client
    client = genai.Client(api_key=api_key)

    # Path to server.py
    server_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
    
    # Configure the MCP server subprocess params
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script]
    )

    print("Connecting to MCP server...")
    
    try:
        # Connect to the MCP Server
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the MCP session
                await session.initialize()
                print("MCP connection established.")
                
                # Fetch available tools from the MCP server
                mcp_tools = await session.list_tools()
                print(f"Registered {len(mcp_tools.tools)} tools from MCP server.")
                
                # Map MCP tools to Gemini Function Declarations
                gemini_tools = []
                for tool in mcp_tools.tools:
                    # Clean up input schema
                    schema = {k: v for k, v in tool.inputSchema.items() if k not in ["additionalProperties", "$schema"]}
                    
                    func_decl = types.FunctionDeclaration(
                        name=tool.name,
                        description=tool.description,
                        parameters=schema
                    )
                    gemini_tools.append(types.Tool(function_declarations=[func_decl]))
                
                # Create a chat session with the tools
                chat = client.chats.create(
                    model="gemini-3.5-flash",
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTIONS,
                        tools=gemini_tools,
                        temperature=0.7,
                        # Disable auto calling so we can execute MCP tools locally
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                    )
                )

                print("\n" + "="*50)
                print("SADAF (Dental Receptionist) is now online.")
                print("Type 'exit' or 'quit' to end the session.")
                print("="*50)
                
                # Get the initial greeting from SADAF
                response = chat.send_message("Hello, please introduce yourself and greet the patient.")
                print(f"\nSADAF: {response.text}")
                
                while True:
                    try:
                        user_input = input("\nYou: ").strip()
                        if not user_input:
                            continue
                        if user_input.lower() in ["exit", "quit", "q"]:
                            print("\nEnding session. Goodbye!")
                            break
                        
                        # Send user message to the Gemini chat
                        response = chat.send_message(user_input)
                        
                        # Loop to handle one or more tool executions requested by Gemini
                        while response.function_calls:
                            response_parts = []
                            for call in response.function_calls:
                                print(f"  [Tool Call: {call.name} | Args: {call.args}]")
                                
                                try:
                                    # Invoke the tool on the MCP server
                                    result = await session.call_tool(call.name, arguments=call.args)
                                    
                                    # Extract result text
                                    result_text = ""
                                    for block in result.content:
                                        if hasattr(block, "text"):
                                            result_text += block.text
                                        elif isinstance(block, dict) and "text" in block:
                                            result_text += block["text"]
                                            
                                    if not result_text:
                                        result_text = str(result)
                                        
                                except Exception as tool_error:
                                    print(f"  [Tool Execution Error: {tool_error}]")
                                    result_text = json.dumps({"error": str(tool_error)})
                                
                                # Package the result as a function response part
                                response_parts.append(
                                    types.Part.from_function_response(
                                        name=call.name,
                                        response={"result": result_text}
                                    )
                                )
                            
                            # Send the tool responses back to the model
                            response = chat.send_message(response_parts)
                        
                        # Print SADAF's final text response
                        print(f"\nSADAF: {response.text}")
                        
                    except (KeyboardInterrupt, EOFError):
                        print("\nSession ended. Goodbye!")
                        break
                    except Exception as loop_err:
                        print(f"\n[Error during chat interaction: {loop_err}]")
                        
    except Exception as mcp_err:
        import traceback
        print(f"\n[Fatal MCP Error]")
        traceback.print_exc()
        print("Make sure you have installed the requirements and that 'server.py' is valid.")

if __name__ == "__main__":
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        pass