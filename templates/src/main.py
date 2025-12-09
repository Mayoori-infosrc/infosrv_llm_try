from phoenix.otel import register
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
import boto3, json, os, time
 
# 1. Register Phoenix OpenTelemetry exporter
tracer_provider = register(
    project_name="llm-test-poc-dev",
    endpoint="http://phoenix-alb-phoenix-stack-dev-2005899370.us-east-1.elb.amazonaws.com/v1/traces",
    auto_instrument=True,
)
tracer = trace.get_tracer("llm-phoenix")
 
# 2. Bedrock setup
session = boto3.Session()
bedrock = session.client("bedrock-runtime")
model_id = "amazon.titan-text-express-v1"
 
 
def call_titan(prompt):
    body = json.dumps({
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 500,
            "temperature": 0.7,
            "topP": 0.9
        }
    })
    response = bedrock.invoke_model(modelId=model_id, body=body)
    data = json.loads(response["body"].read())
    return data["results"][0]["outputText"].strip()
 
 
# 3. Chat loop
print("Chat with Titan (type 'quit' to exit)")
while True:
    user_input = input("You: ").strip()
    if user_input.lower() in ["quit", "exit"]:
        print("👋 Exiting. Check Phoenix for traces.")
        break
    if not user_input:
        continue
 
    # Root trace span
    with tracer.start_as_current_span("chat.session", kind=SpanKind.SERVER) as root:
        root.set_attribute("service.name", "titan-phoenix-chatbot")
 
        # Child span for Titan inference
        with tracer.start_as_current_span("amazon.titan.inference", kind=SpanKind.CLIENT) as span:
            span.set_attribute("llm.provider", "amazon-bedrock")
            span.set_attribute("llm.model_name", model_id)
            # Serialize structured data as strings
            span.set_attribute("llm.input_messages", json.dumps([{"role": "user", "content": user_input}]))
 
            start = time.time()
            try:
                output = call_titan(user_input)
                latency = time.time() - start
 
                # Output also serialized
                span.set_attribute("llm.output_messages", json.dumps([{"role": "assistant", "content": output}]))
                span.set_attribute("response.time.ms", round(latency * 1000, 2))
                span.set_status(Status(StatusCode.OK))
 
                print(f"Bot: {output}\n")
 
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error.message", str(e))
                print(f" Error: {e}")