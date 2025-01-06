## TODO

I have TODOs scattered across the codebase, but these are the important TODOs that come to mind

## P0
I want to test my service that I wrote (I usually somewhat subscribe to Kent Beck's [TOD](https://www.oreilly.com/library/view/test-driven-development/0321146530/)). Usually I write the tests before I write the implementation (or at least alongside it). However, because of the time pressure, I just went ahead without them. This does mean decreased confidence in all the edge cases for the APIs.

- [ ] **Unit Tests**
- [ ] **E2E Tests**

## P1
- [ ] **ID Lookup Table:** I haven't seen mistakes yet, but I think that it would be good to convert all ids into random words with the three-random-words method.
- [ ] **Improve UI Layout:** Write some cleaner UI and spend some time getting the advice of users on the layout
- [ ] **Prompting improvements** 
  - [ ] **Error Message Prompts:** I took some time to develop nice prompts for the instructions and tool calls, but I want to analyze the error messages I am passing back to the assistant and make sure they are detailed enough
  - [ ] **Ablation of Instructions:** Check what parts of my prompts are important and remove those parts that are not important.
- [ ] **Cache Images themselves:** I mentioned the issue with google images in [INFO.md](https://github.com/sachiniyer/meal-finder/blob/master/INFO.md#qa). I want to download the google images and upload them to S3 so that the chat can access them better
- [ ] **Cleaner serialization method to natural language:** I want to write a serialization module like I did [here](https://github.com/sachiniyer/order-assistant/blob/e2ec02e586aec6724cc3b706293bfcaf1f8d1d26/src/order.rs#L26) so that my response body are converted to natural language in a highly configurable way.
- [ ] **Write basic evaluation method:** Write some basic evaluation method that I can use to judge my system against.

## P2
#### Project
- [ ] **Integrate with a menu provider:** I wanted to do this originally, but it costed too much (more details in [INFO.md](https://github.com/sachiniyer/meal-finder/blob/master/INFO.md#qa))
- [ ] **Add a real authentication mechanism:** Integrate with some oauth providers like google/github
- [ ] **Better citation method:** My citation method leaves something be desired, improve this.

#### Project Configuration
- [ ] **More resilient deployment:** This project with probably live on [my cluster](https://wiki.sachiniyer.com/#!index.md), so I need to write the yaml files for a kubernetes deployment
- [ ] **Clean up the build system**
- [ ] **Write github actions to run unit tests/E2E tests** 
- [ ] **Clean up `requirements.txt`**
- [ ] **Format code on Pull Request**
- [ ] **Autodeployments to vercel from Github**
...

## P3
- [ ] **Stop one-off indexing and index restaurants beforehand:** I would love to actually aggregate all the information from the API sources and add that to an index. However, that would have been too costly for this project/would have taken too long. I think that is a necessary addition however to turn it into a product.
- [ ] **Store User Preferences:** I didn't do this for this project (would have a been a simple add given my architecture). I don't have user authentication yet so I did not think it made sense to add in.
- [ ] **Write a more advanced evaluation method (e.g. llm-as-a-judge):** Writing a real evaluation method is hard but necessary to figure out where my system's weaknesses are
