# Meal Finder

An application that runs through an LLM agent to find you meals using various APIs and other LLMs

Currently hosted at https://meal-finder-alpha.vercel.app/ (email me for API key, because OpenAI is too expensive - https://sachiniyer.com/contact )

For more info about the project, look at [INFO.md](./INFO.md). For what I still want to fix [TODO.md](./TODO.md)

# Commands

## To run full dev
1. Fill out `.env`
2. Run `docker-compose -f backend/docker-compose.dev.yml up -d`
3. Run `pip install -r backend/requirements.txt`
4. Run `flask run --port 8000 --debug`
5. spawn new shell and `cd frontend`
6. `npm install`
7. `npm run dev`

## To just run dev on the frontend
1. add `NEXT_PUBLIC_BACKEND_URL=https://mealsapi.sachiniyer.com` to `frontend/.env.development.local`
2. `npm install`
3. `npm run dev`

## To run the prod version of backend
1. Fill out `.env`
2. `docker-compose up -d`

## To deploy the frontend
1. `vercel --prod`
