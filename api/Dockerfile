FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    FUNCTIONS_WORKER_RUNTIME=python

WORKDIR /home/site/wwwroot

# Cache dependencies separately
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Azure Functions source: function_app.py, host.json, shared/
COPY api/ .

EXPOSE 80