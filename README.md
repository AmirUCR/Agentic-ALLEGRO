# Introduction
Our collaborators found configuring [ALLEGRO](https://github.com/ucrbioinfo/ALLEGRO) for their experiments too daunting of a task. So I made a Claude AI assistant for it.

ALLEGRO has a big and maybe confusing [config](https://github.com/AmirUCR/allegro-data/blob/master/config.yaml) – In an ideal world, you describe your experimental needs to the ghost in the machine, and [It Just Works™](https://youtu.be/qmPq00jelpc?t=8)

Here's how it works:
1. Get an [Anthropic API key](https://platform.claude.com/) (you need $5 for this) and SAVE it
1. Set your API key for this terminal session: `export ANTHROPIC_API_KEY=sk-ant-api...`
1. Clone this repo
1. Change directory `cd Agentic-ALLEGRO`
1. Install the dependencies `pip install anthropic allegro-bio`
1. Download the [ALLEGRO Jumpstart dataset](https://github.com/AmirUCR/allegro-data) `git clone https://github.com/AmirUCR/allegro-data.git`
1. Run Claude x ALLEGRO `python main.py`
1. You are now talking to Claude. Ask it to `describe ALLEGRO's parameters`
1. Once you read what options there are, explain where your input is, and how you want your experiment set up. Here's what I did: 
    >"my input is under allegro-data/data/input/example_input/ - manifest under allegro-data/data/input/two.csv - experiment is cas9 with NGG and multi = 2 - track e - no offtarget analysis, no scoring"
1. Sit back and watch the magic happen

https://github.com/user-attachments/assets/ccd6902c-02e1-4d19-b472-672d317ae5db

If the embedded video above doesn't work, here's a [mirror](https://www.youtube.com/watch?v=zPyxFvZS4ms)

# Support
If you run into any issues or have suggestions for Agentic ALLEGRO, please report them on our GitHub Issues tracker. It's the fastest way to get support and helps us improve Agentic ALLEGRO for everyone.

# About
Agentic ALLEGRO has been developed and is maintained by <ins>Amir</ins>sadra Mohseni at the University of California, Riverside.
