FROM python:3.10-slim

# Install system dependencies for OpenCV and Node.js
RUN apt-get update && apt-get install -y \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    nodejs \
    npm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up Python Engine dependencies
WORKDIR /app/python-engine
COPY python-engine/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Set up Node Backend dependencies
WORKDIR /app/node-backend
COPY node-backend/package*.json ./
RUN npm install

# Expose the API port
EXPOSE 3000

# We use nodemon for dev
CMD ["npm", "run", "dev"]
