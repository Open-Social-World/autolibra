FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy the backend directory
COPY inspicio_backend/ ./

# Copy the required osw_data package
COPY packages/ ./packages/

# Copy required data directories
COPY .data/ ./.data/

# Install dependencies
RUN pip install fastapi uvicorn[standard] psycopg2-binary pydantic

# Expose the port Railway will use
EXPOSE 8000

# Run the server
CMD ["python", "server.py"]