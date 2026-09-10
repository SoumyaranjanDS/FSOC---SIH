FROM node:20-alpine

WORKDIR /app

# Install dependencies first for Docker caching
COPY package*.json ./
RUN npm install

# Expose Vite's default port
EXPOSE 5173

# Run Vite in dev mode
CMD ["npm", "run", "dev"]
