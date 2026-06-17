FROM node:22-alpine

RUN useradd -m front_user

WORKDIR /app

COPY package*.json ./
RUN npm install

RUN chown -R front_user:front_user /app
USER front_user

COPY --chown=front_user:front_user . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host"]