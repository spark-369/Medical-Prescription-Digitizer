FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json* .npmrc ./
RUN npm ci --loglevel=error || npm install --loglevel=error

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
