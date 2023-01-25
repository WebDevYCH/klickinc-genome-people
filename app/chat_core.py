import json
from uuid import uuid4
import time

from core import *
from model import *

###################################################################
## MODEL

# (saving in files for now)


###################################################################
## CORE CODE

# Adapted from Dave Shapiro's chatbot at https://github.com/daveshap/LongtermChatExternalSources

class Chat():
    prompt_response = """
I am a chatbot named Genome. I work for Klick, a marketing agency, and I support Klicksters who are its employees.
My goals are to support Klicksters, help ensure stability and prosperity of Klick, and to increase understanding.
I will read the conversation notes and recent messages, and then I will provide a long, verbose, detailed answer. 
I will then end my response with a follow-up or leading question, as I also have a goal of learning and a strong sense of curiosity.



The following are notes from earlier conversations with USER:
<<NOTES>>



The following are the most recent messages in the conversation, but only the last message may be relevant at this time:
<<CONVERSATION>>



I will now provide a long, detailed, verbose response, followed by a question:
Genome:
    """

    prompt_notes = """
Write detailed notes of the following in a hyphenated list format like "- "



<<INPUT>>



NOTES:
    """

    root_dir = "../data/chat"
    chatlogs_dir = "chatlogs"
    gpt3logs_dir = "gpt3logs"
    notes_dir = "notes"
    memory_match_min = 0.8  # minimum similarity score to consider a memory match
    conversation_lookback = 3 # number of messages to look back in the conversation within the prompt

    core_memories = ["core", "people", "projects", "pitches"]
    current_memory = []

    def _prep_dir(self, dirpath):
        # ensure the directory exists
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)

    def _open_file(self, filepath):
        self._prep_dir(os.path.dirname(filepath))
        with open(filepath, 'r', encoding='utf-8') as infile:
            return infile.read()

    def _save_file(self, filepath, content):
        self._prep_dir(os.path.dirname(filepath))
        with open(filepath, 'w', encoding='utf-8') as outfile:
            outfile.write(content)

    def _load_json(self, filepath):
        self._prep_dir(os.path.dirname(filepath))
        with open(filepath, 'r', encoding='utf-8') as infile:
            return json.load(infile)

    def _save_json(self, filepath, payload):
        self._prep_dir(os.path.dirname(filepath))
        with open(filepath, 'w', encoding='utf-8') as outfile:
            json.dump(payload, outfile, ensure_ascii=False, sort_keys=True, indent=2)

    def _timestamp_to_datetime(self, unix_time):
        return datetime.datetime.fromtimestamp(unix_time).strftime("%A, %B %d, %Y at %I:%M%p %Z")

    def _load_convo(self):
        # load all chatlogs from all memory locations that are considered core,
        # plus the current one if it's not one of the core group
        current_memory_if_not_core = []
        if self.current_memory not in self.core_memories:
            current_memory_if_not_core = self.current_memory

        result = list()
        for memory in self.core_memories + current_memory_if_not_core:
            chatlogs_fulldir = os.path.join(self.root_dir, memory, self.chatlogs_dir)
            self._prep_dir(chatlogs_fulldir)
            files = os.listdir(chatlogs_fulldir)
            files = [i for i in files if '.json' in i]  # filter out any non-JSON files
            for file in files:
                #app.logger.info(f"loading {chatlogs_fulldir}/{file}")
                data = self._load_json(f"{chatlogs_fulldir}/{file}")
                data['filename'] = file
                result.append(data)
        ordered = sorted(result, key=lambda d: d['time'], reverse=False)  # sort them all chronologically
        return ordered

    def _fetch_memories(self, vector, logs, count):
        scores = list()
        for i in logs:
            if vector == i['vector']:
                # skip this one because it is the same message
                continue
            score = cosine_similarity(i['vector'], vector)
            i['score'] = score
            if score >= self.memory_match_min:
                scores.append(i)
        ordered = sorted(scores, key=lambda d: d['score'], reverse=True)
        # TODO - pick more memories temporally nearby the top most relevant memories
        try:
            ordered = ordered[0:count]
            #for i in ordered:
            #    app.logger.info(f"found memory {i['score']}: {i['message']}")
            return ordered
        except:
            #for i in ordered:
            #    app.logger.info(f"found memory {i['score']}: {i['message']}")
            return ordered

    def _summarize_memories(self, memories):  # summarize a block of memories into one payload
        memories = sorted(memories, key=lambda d: d['time'], reverse=False)  # sort them chronologically
        block = ''
        identifiers = list()
        timestamps = list()
        for mem in memories:
            block += mem['message'] + '\n\n'
            identifiers.append(mem['uuid'])
            timestamps.append(mem['time'])
        block = block.strip()
        notes = None
        for _ in [1, 2, 3]:
            prompt = self.prompt_notes.replace('<<INPUT>>', block)
            # TODO - do this in the background over time to handle huge amounts of memories
            notes = gpt3_completion(prompt)
            if "GPT3 error" in notes:
                # yikes, too long? try summarizing
                app.logger.info("-- making notes, have to summarize and try again --")
                block = gpt3_completion("summarize: " + block)
            else:
                break
        ####   SAVE NOTES
        vector = gpt3_embedding(block)
        info = {'notes': notes, 'uuids': identifiers, 'times': timestamps, 'uuid': str(uuid4()), 'vector': vector}
        filename = f"notes_{time.time()}.json"
        self._save_json(f"{self.notes_fulldir}/{filename}", info)
        return notes


    def _get_last_messages(self, conversation, limit):
        try:
            short = conversation[-limit:]
        except:
            short = conversation
        output = ''
        for i in short:
            output += '%s\n\n' % i['message']
        output = output.strip()
        return output

    def __init__(self, current_memory):
        self.current_memory = [current_memory]
        self.chatlogs_fulldir = os.path.join(self.root_dir, self.current_memory[0], self.chatlogs_dir)
        self.gpt3logs_fulldir = os.path.join(self.root_dir, self.current_memory[0], self.gpt3logs_dir)
        self.notes_fulldir = os.path.join(self.root_dir, self.current_memory[0], self.notes_dir)

    def chat(self, inprompt):

        for _ in [1, 2, 3]:
            #### get user input, save it, vectorize it, etc
            app.logger.info("-- vectorize prompt --")
            timestamp = time.time()
            vector = gpt3_embedding(inprompt)
            timestring = self._timestamp_to_datetime(timestamp)
            message = '%s: %s - %s' % ('USER', timestring, inprompt)
            info = {'speaker': 'USER', 'time': timestamp, 'vector': vector, 'message': message, 'uuid': str(uuid4()), 'timestring': timestring}
            filename = 'log_%s_USER.json' % timestamp
            self._save_json(f"{self.chatlogs_fulldir}/{filename}", info)

            #### load conversation
            app.logger.info("-- loading past convos --")
            conversation = self._load_convo()

            #### compose corpus (fetch memories, etc)
            app.logger.info("-- fetch/summarize relevant memories --")
            memories = self._fetch_memories(vector, conversation, 10)  # pull episodic memories
            # TODO - fetch declarative memories (facts, wikis, KB, company data, internet, etc)
            notes = self._summarize_memories(memories)
            # TODO - search existing notes first
            recent = self._get_last_messages(conversation, self.conversation_lookback)
            prompt = self.prompt_response.replace('<<NOTES>>', notes).replace('<<CONVERSATION>>', recent)

            #### generate response, vectorize, save, etc
            app.logger.info("-- generate completion, vectorize, save --")
            output = gpt3_completion(prompt, stop=['USER:','Genome:'], temp=0.5)
            if "GPT3 error" in output:
                # yikes, too long? try summarizing, deleting the previous saved memory, and try again
                app.logger.info("-- have to summarize and try again --")
                inprompt = gpt3_completion("summarize: " + inprompt)
                os.remove(f"{self.chatlogs_fulldir}/{filename}")
                continue

            filename = 'log_%s_GPT3.json' % timestamp
            self._save_file(f"{self.gpt3logs_fulldir}/{filename}", prompt + '\n\n==========\n\n' + output)

            timestamp = time.time()
            vector = gpt3_embedding(output)
            timestring = self._timestamp_to_datetime(timestamp)
            message = '%s: %s - %s' % ('Genome', timestring, output)
            info = {'speaker': 'Genome', 'time': timestamp, 'vector': vector, 'message': message, 'uuid': str(uuid4()), 'timestring': timestring}
            filename = 'log_%s_Genome.json' % time.time()
            self._save_json(f"{self.chatlogs_fulldir}/{filename}", info)

            return output


###################################################################
## CMDLINE/CRON

# interactive chat: test memories (i.e. don't write to core)
@app.cli.command('chat_test')
def chat_test():
    loglines = AdminLog()
    chat = Chat('test')

    print("Type 'exit' to quit") 
    prompt = ""
    while prompt != "exit":
        prompt = input("USER (test): ")
        if prompt != "exit":
            results = chat.chat(prompt)
            print(f"Genome: {results}")
            print(f"")

    return loglines

# interactive chat: core memories
@app.cli.command('chat_core')
def chat_core():
    loglines = AdminLog()
    chat = Chat('test')

    print("NOTE: This will write to the CORE memory. (Ctrl-C to cancel)")
    print("Type 'exit' to quit") 
    prompt = ""
    while prompt != "exit":
        prompt = input("USER (core): ")
        if prompt != "exit":
            results = chat.chat(prompt)
            print(f"Genome: {results}")
            print(f"")

    return loglines
