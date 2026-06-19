# Stage 1: Build the React application
FROM node:20-alpine as builder

WORKDIR /app

# Copy package files and install dependencies
COPY package*.json bun.lockb* ./
# Since there is a bun.lockb, let's just use npm ci or npm install
RUN npm install

# Copy source code and build
COPY . .
RUN npm run build

# Stage 2: Serve the application with Nginx
FROM nginx:alpine

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port (Cloud Run sets PORT env var)
EXPOSE 8080

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
