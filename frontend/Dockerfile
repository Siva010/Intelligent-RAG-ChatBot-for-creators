FROM node:20-slim

WORKDIR /app

# Copy only package.json to force re-resolving optional dependencies for Linux
COPY package.json ./
RUN npm install

COPY . .

RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
