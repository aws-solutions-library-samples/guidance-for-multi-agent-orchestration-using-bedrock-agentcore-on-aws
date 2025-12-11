FROM --platform=linux/arm64 python:3.13-slim

# Install dependencies with OTEL support
RUN pip install 'strands-agents[a2a]' bedrock-agentcore boto3 'aws-opentelemetry-distro>=0.10.0'

# Create non-root user (security requirement)
RUN groupadd -g 1001 appgroup && \
    useradd -m -u 1001 -g appgroup appuser

# Switch to non-root user
USER appuser

# Copy agent files
COPY agent.py /app/agent.py
COPY system_prompt.py /app/system_prompt.py

WORKDIR /app

# Expose AgentCore Runtime port
EXPOSE 8080

# Health check using AgentCore Runtime /ping endpoint
HEALTHCHECK CMD curl -f http://localhost:8080/ping || exit 1

# Set environment variable for unbuffered output
ENV PYTHONUNBUFFERED=1

# Run agent with OpenTelemetry instrumentation for default OTEL logging
CMD ["opentelemetry-instrument", "python", "agent.py"]
