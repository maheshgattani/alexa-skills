# -*- coding: utf-8 -*-

import random
import logging
import os
import boto3
import urllib
import json
from datetime import datetime

from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model import Response
from ask_sdk_s3.adapter import S3Adapter

SKILL_NAME = 'Trivia Game'
MAXIMUM_ATTEMPTS = 2
TOTAL_QUESTIONS = 5
WELCOME_TEXT = "Welcome to the Trivia game. You will be asked " + str(TOTAL_QUESTIONS) + " multiple choice questions during the game. You will get " + str(MAXIMUM_ATTEMPTS) + " attempts to answer each question. Anytime during the game, you can ask to repeat the question or ask for your score. Would you like to play?"
NEXT_QUESTION_STRING = "Say next question to continue."
CATEGORIES = {
9: "General Knowledge",
10: "Books",
11: "Film",
12: "Music",
14: "Television",
15: "Video Games",
17: "Science & Nature",
18: "Computers",
22: "Geography",
23: "History",
31: "Japanese Anime & Manga",
}

bucket_name = os.environ.get('S3_PERSISTENCE_BUCKET')
s3_client = boto3.client('s3',
                         region_name=os.environ.get('S3_PERSISTENCE_REGION'),
                         config=boto3.session.Config(signature_version='s3v4',s3={'addressing_style': 'path'}))
s3_adapter = S3Adapter(bucket_name=bucket_name, path_prefix="Media", s3_client=s3_client)
sb = CustomSkillBuilder(persistence_adapter=s3_adapter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@sb.request_handler(can_handle_func=is_request_type("LaunchRequest"))
def launch_request_handler(handler_input):
    """Handler for Skill Launch.

    Get the persistence attributes, to figure out the game state.
    """
    # type: (HandlerInput) -> Response
    attr = handler_input.attributes_manager.persistent_attributes
    if not attr:
        attr['ended_session_count'] = 0
        attr['game_state'] = 'ENDED'

    handler_input.attributes_manager.session_attributes = attr

    speech_text = WELCOME_TEXT
    reprompt = "Say yes to start the game or no to quit."

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


def help_response(session_attr):
    speech_text = ""
    if 'game_state' in session_attr and session_attr['game_state'] == "STARTED":
        if session_attr["ongoing_question"] == 1:
            speech_text = "Say repeat question to hear the question again."
        else:
            speech_text = "Say next question to hear the next question."
    elif "selection_requested" in session_attr:
        if session_attr["selection_requested"] == "category":
            speech_text = "Do you want to select a category? You can select a category like Film or Books. You can skip selection. Questions from all the categories will be selected. Or you can ask about the available categories. "
        elif session_attr["selection_requested"] == "difficulty":
            speech_text = "Do you want to select a difficulty level? You can select easy, medium or hard. Or you can skip selection. Difficulty level will default to easy."
        else:
            speech_text = "Say yes to start the game or no to quit."
    else:
        speech_text = "Say yes to start the game or no to quit."

    return speech_text


@sb.request_handler(can_handle_func=is_intent_name("AMAZON.HelpIntent"))
def help_intent_handler(handler_input):
    """Handler for Help Intent."""
    # type: (HandlerInput) -> Response
    session_attr = handler_input.attributes_manager.session_attributes
    speech_text = help_response(session_attr)
    reprompt = speech_text
    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


@sb.request_handler(
    can_handle_func=lambda input:
        is_intent_name("AMAZON.CancelIntent")(input) or
        is_intent_name("AMAZON.StopIntent")(input))
def cancel_and_stop_intent_handler(handler_input):
    """Single handler for Cancel and Stop Intent."""
    # type: (HandlerInput) -> Response
    speech_text = "Thanks for playing!!"

    handler_input.response_builder.speak(
        speech_text).set_should_end_session(True)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_request_type("SessionEndedRequest"))
def session_ended_request_handler(handler_input):
    """Handler for Session End."""
    # type: (HandlerInput) -> Response
    logger.info(
        "Session ended with reason: {}".format(
            handler_input.request_envelope.request.reason))
    return handler_input.response_builder.response


def ongoing_game_response(session_attr):
    speech_text = "There is an ongoing game. "
    if session_attr["ongoing_question"] == 1:
        speech_text = speech_text + " Say repeat question to hear the question again."
    else:
        speech_text = speech_text + " Say next question to hear the next question."
    return speech_text


@sb.request_handler(can_handle_func=lambda input:
                    is_intent_name("AMAZON.YesIntent")(input))
def yes_handler(handler_input):
    """Handler for Yes Intent, only if the player said yes for
    a new game.
    """
    # type: (HandlerInput) -> Response
    session_attr = handler_input.attributes_manager.session_attributes
    if 'game_state' in session_attr and session_attr['game_state'] == "STARTED":
        speech_text = ongoing_game_response(session_attr)
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

    session_attr["selection_requested"] = "category"
    speech_text = "Do you want to select a category? You can select a category like Film or Books. You can skip selection. Questions from all the categories will be selected. Or you can ask about the available categories. "
    handler_input.response_builder.speak(speech_text).ask(speech_text)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=lambda input:
                    not currently_playing(input) and
                    is_intent_name("SkipSelection")(input))
def skip_selection_handler(handler_input):
    session_attr = handler_input.attributes_manager.session_attributes
    if "selection_requested" not in session_attr or (session_attr["selection_requested"] != "category" and session_attr["selection_requested"] != "difficulty"):
        speech_text = "You can not skip at this time. Try using help for next step."
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response
        
    if session_attr["selection_requested"] == "category":
        speech_text = "Do you want to select a difficulty level? You can select easy, medium or hard. Or you can skip selection. Difficulty level will default to easy."
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        session_attr["selection_requested"] = "difficulty"
        return handler_input.response_builder.response
    else:
        speech_text, reprompt, session_attr = start_game(session_attr, "easy")    
        handler_input.response_builder.speak(speech_text).ask(reprompt)
        del session_attr["selection_requested"]
        return handler_input.response_builder.response


def sample_category_response():
    available_categories = [v for k,v in CATEGORIES.items()]
    random.seed(datetime.now())
    random.shuffle(available_categories)
    speech_text = "Here is a sample list of categories to choose from: " + ", ".join(available_categories[0:4])
    return speech_text


@sb.request_handler(can_handle_func=lambda input:
                    not currently_playing(input) and
                    is_intent_name("CategoryIntent")(input))
def categories_handler(handler_input):
    session_attr = handler_input.attributes_manager.session_attributes
    category = handler_input.request_envelope.request.intent.slots["category"].value
    if not category:
        speech_text = sample_category_response()
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

    category_id = None
    for k,v in CATEGORIES.items():
        if category in v.lower():
            category = v
            category_id = k
            break
        
    if not category_id:
        speech_text = sample_category_response()
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response
        
    session_attr["category_id"] = category_id
    session_attr["selection_requested"] = "difficulty"
    speech_text = "Great! You have selected the " + category + " category. Do you want to select a difficulty level? You can select easy, medium or hard. Or you can skip selection. Difficulty level will default to easy."
    handler_input.response_builder.speak(speech_text).ask(speech_text)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=lambda input:
                    is_intent_name("DifficultyIntent")(input))
def difficulty_handler(handler_input):
    session_attr = handler_input.attributes_manager.session_attributes
    difficulty = handler_input.request_envelope.request.intent.slots["difficulty"].value
    if "eas" in difficulty:
        difficulty = "easy"
    elif "hard" in difficulty:
        difficulty = "hard"
    elif "medium" in difficulty:
        difficulty = "medium"
    else:
        speech_text = "You can select easy, medium or hard. Or you can skip selection. Difficulty level will default to easy."
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response
        
    del session_attr["selection_requested"]
    speech_text, reprompt, session_attr = start_game(session_attr, difficulty)    
    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


def start_game(session_attr, difficulty):
    trivia = get_trivia(difficulty, session_attr["category_id"] if "category_id" in session_attr else None )

    session_attr['game_state'] = "STARTED"
    session_attr["trivia"] = trivia
    session_attr["difficulty"] = difficulty
    session_attr["attempts"] = 0
    session_attr["incorrect_answers"] = 0 
    session_attr["correct_answers"] = 0 
    session_attr["current_question_index"] = 0
    session_attr["ongoing_question"] = 1

    current_question_index = 0

    question, options, options_text = get_question_and_answers(trivia, current_question_index)
    session_attr["current_question_options"] = options
    speech_text = "Great! Here is the first question. " + question + options_text
    reprompt = "Here is the first question. " + question + options_text
    
    return speech_text, reprompt, session_attr


@sb.request_handler(can_handle_func=lambda input:
                    currently_playing(input) and
                    is_intent_name("ScoreIntent")(input))
def score_intent_handler(handler_input):
    session_attr = handler_input.attributes_manager.session_attributes
    speech_text = score_string(session_attr)
    if session_attr["ongoing_question"] == 1:
        speech_text = speech_text + " Say repeat question to hear the question again."
    else:
        speech_text = speech_text + " Say next question to hear the next question."

    handler_input.response_builder.speak(speech_text).ask(speech_text)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=lambda input:
                    currently_playing(input) and
                    is_intent_name("AMAZON.NextIntent")(input))
def next_intent_handler(handler_input):
    """Handler for Next Intent, only if the player said yes for
    a new game.
    """
    # type: (HandlerInput) -> Response
    session_attr = handler_input.attributes_manager.session_attributes
    if session_attr["ongoing_question"] == 1:
        speech_text = "There is an ongoing question. Say repeat question to hear it."
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response
        
    trivia = session_attr["trivia"]
    
    # Move the pointer to next question
    current_question_index = session_attr["current_question_index"] + 1
    session_attr["current_question_index"] = current_question_index

    if len(trivia["results"]) > current_question_index:
        question, options, options_text = get_question_and_answers(trivia, current_question_index)
        session_attr["current_question_options"] = options
        speech_text = "Okay! " + question + options_text
        reprompt = question + options_text
        session_attr["ongoing_question"] = 1
    else:
        del session_attr['game_state']
        speech_text = final_speech_text(session_attr)
        reprompt = speech_text
        session_attr["current_question_index"] = 0
        session_attr["incurrent_question_index"] = 0    
        session_attr["ongoing_question"] = 0
    
    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=lambda input:
                    is_intent_name("AMAZON.RepeatIntent")(input))
def repeat_intent_handler(handler_input):
    """Handler for Repeat Intent, only if the player said yes for
    a new game.
    """
    # type: (HandlerInput) -> Response
    session_attr = handler_input.attributes_manager.session_attributes
    if 'game_state' in session_attr and session_attr['game_state'] == "STARTED" and session_attr["ongoing_question"] == 1:
        trivia = session_attr["trivia"]
        current_question_index = session_attr["current_question_index"]
        options = session_attr["current_question_options"]
        options_enumerate = enumerate(options, start=1)
        options_text = " Is it: " 
        for index, option in options_enumerate:
            options_text = options_text + "(" + str(index) + ": " + option + "). " 

        question = trivia["results"][current_question_index]["question"]
        speech_text = "Okay! " + question + options_text
        reprompt = question + options_text
    else:
        speech_text = help_response(session_attr)

    handler_input.response_builder.speak(speech_text).ask(speech_text)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=lambda input:
                    not currently_playing(input) and
                    is_intent_name("AMAZON.NoIntent")(input))
def no_handler(handler_input):
    """Handler for No Intent, only if the player said no for
    a new game.
    """
    # type: (HandlerInput) -> Response
    session_attr = handler_input.attributes_manager.session_attributes
    session_attr['game_state'] = "ENDED"
    session_attr['ended_session_count'] += 1

    handler_input.attributes_manager.persistent_attributes = session_attr
    handler_input.attributes_manager.save_persistent_attributes()

    speech_text = "Ok. See you next time!!"

    handler_input.response_builder.speak(speech_text)
    return handler_input.response_builder.response

def selection_requested_response(session_attr):
    speech_text = "Sorry I did not understand that. "
    if session_attr["selection_requested"] == "category":
        speech_text = speech_text + "You can select a category like Film or Books. You can skip selection. Questions from all the categories will be selected. Or you can ask about the available categories."
    else:
        speech_text = speech_text + "You can select easy or medium or hard. Or you can skip selection. Difficulty level will default to easy."
    return speech_text


@sb.request_handler(can_handle_func=lambda input:
                    is_intent_name("TriviaIntent")(input))
def trivia_handler(handler_input):
    """Handler for processing guess with target."""
    # type: (HandlerInput) -> Response
    session_attr = handler_input.attributes_manager.session_attributes
    trivia = session_attr["trivia"]
    
    if 'game_state' not in session_attr or session_attr['game_state'] != "STARTED" or session_attr["ongoing_question"] != 1:
        if "selection_requested" in session_attr:
            speech_text = selection_requested_response(session_attr)
            handler_input.response_builder.speak(speech_text).ask(speech_text)
            return handler_input.response_builder.response
        else:
            speech = "Sorry I could not understand that. Say help to continue or no to end the game!!"
            handler_input.response_builder.speak(speech).ask(speech)
            return handler_input.response_builder.response

    answer_number = int(handler_input.request_envelope.request.intent.slots["number"].value)
    answer = handler_input.request_envelope.request.intent.slots["answer"].value

    # Capture cases where intent read the slots wrong
    if answer == "one" or answer == "1":
        answer_number = 1
    elif answer == "two" or answer == "to" or answer == "too" or answer == "2":
        answer_number = 2
    elif answer == "three" or answer == "3":
        answer_number = 3
    elif answer == "four" or answer == "for" or answer == "4":
        answer_number = 4
        
    if not answer_number:
        speech_text = "Sorry, I did not understand that. Try saying (is it option) before your answer. Please try again."
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

    current_question_index = session_attr["current_question_index"]
    correct_answer = trivia["results"][current_question_index]["correct_answer"]
    current_question_options = session_attr["current_question_options"]
    
    if answer_number <= len(current_question_options):
        answer = current_question_options[answer_number - 1]
        speech_text, reprompt, session_attr = check_answer(answer, correct_answer, session_attr)
        handler_input.response_builder.speak(speech_text).ask(reprompt)
        return handler_input.response_builder.response
    else:
        speech_text = "Please try again with one of the options in the question."
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response


@sb.request_handler(can_handle_func=lambda input:
                    is_intent_name("TriviaAnswerIntent")(input))
def trivia_answer_handler(handler_input):
    """Handler for processing guess with target."""
    # type: (HandlerInput) -> Response
    session_attr = handler_input.attributes_manager.session_attributes
    if 'game_state' not in session_attr or session_attr['game_state'] != "STARTED" or session_attr["ongoing_question"] != 1:
        if "selection_requested" in session_attr:
            speech_text = selection_requested_response(session_attr)
            handler_input.response_builder.speak(speech_text).ask(speech_text)
            return handler_input.response_builder.response
        else:
            speech = "Sorry I could not understand that. Say help to continue or no to end the game!!"
            handler_input.response_builder.speak(speech).ask(speech)
            return handler_input.response_builder.response
    
    answer = handler_input.request_envelope.request.intent.slots["answer"].value
    if not answer:
        speech_text = "Sorry, I did not understand that. Try saying something like (is it option 3) as your answer. You can ask me to repeat the question. Please try again."
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

    # Capture cases where intent read the slots wrong
    answer_number = None
    if answer == "one" or answer == "1":
        answer_number = 1
    elif answer == "two" or answer == "to" or answer == "too" or answer == "2":
        answer_number = 2
    elif answer == "three" or answer == "3":
        answer_number = 3
    elif answer == "four" or answer == "for" or answer == "4":
        answer_number = 4
        
    trivia = session_attr["trivia"]
    current_question_index = session_attr["current_question_index"]
    correct_answer = trivia["results"][current_question_index]["correct_answer"]
    current_question_options = session_attr["current_question_options"]

    if answer_number:
        answer = current_question_options[answer_number - 1]

    speech_text, reprompt, session_attr = check_answer(answer, correct_answer, session_attr)
    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=lambda input: True)
def unhandled_intent_handler(handler_input):
    """Handler for all other unhandled requests."""
    # type: (HandlerInput) -> Response
    speech = "Sorry I could not understand that. Say help to continue or no to end the game!!"
    handler_input.response_builder.speak(speech).ask(speech)
    return handler_input.response_builder.response


@sb.exception_handler(can_handle_func=lambda i, e: True)
def all_exception_handler(handler_input, exception):
    """Catch all exception handler, log exception and
    respond with custom message.
    """
    # type: (HandlerInput, Exception) -> Response
    logger.error(exception, exc_info=True)
    speech = "Sorry there was a problem with the skill. We are working on fixing it. Please try playing again in some time. "
    handler_input.response_builder.speak(speech).ask(speech)
    return handler_input.response_builder.response


def check_alpha_or_space(answer):
    for character in answer:
        if not (character.isalpha() or character.isspace()):
            return False
    return True


def get_trivia(difficulty, category_id):
    url = "https://opentdb.com/api.php?amount=20&type=multiple"
    url = url + "&difficulty=" + difficulty
    if category_id:
        url = url + "&category=" + str(category_id)
    logger.info("Trivia url: {}".format(url))
    operUrl = urllib.request.urlopen(url)
    if(operUrl.getcode()==200):
        data = operUrl.read()
        jsonData = json.loads(data)
        good_questions = []
        for result in jsonData["results"]:
            good_question = True
            if not check_alpha_or_space(result["correct_answer"]):
                continue
            
            for incorrect_answer in result["incorrect_answers"]:
                if not check_alpha_or_space(incorrect_answer):
                    good_question = False
                    break
            if good_question:
                good_questions.append(result)
                
            if len(good_questions) == TOTAL_QUESTIONS:
                break
        jsonData["results"] = good_questions
        return jsonData
    else:
        print("Error receiving data", operUrl.getcode())
        return {}


def currently_playing(handler_input):
    """Function that acts as can handle for game state."""
    # type: (HandlerInput) -> bool
    is_currently_playing = False
    session_attr = handler_input.attributes_manager.session_attributes

    if ("game_state" in session_attr
            and session_attr['game_state'] == "STARTED"):
        is_currently_playing = True

    return is_currently_playing

def get_question_and_answers(trivia, current_question_index):
    options = trivia["results"][current_question_index]["incorrect_answers"]
    options.append(trivia["results"][current_question_index]["correct_answer"])
    random.seed(datetime.now())
    random.shuffle(options)
    options = list(set(options))
    
    options_enumerate = enumerate(options, start=1)
    options_text = " Is it: " 
    for index, option in options_enumerate:
        if index == 1:
            options_text = options_text + "(" + str(index) + ": " + option + "). " 
        else:
            options_text = options_text + "(" + str(index) + ": " + option + "). "
    
    question = trivia["results"][current_question_index]["question"]
    
    return question, options, options_text


def score_string(session_attr):
    return "Your score is " + str(session_attr["correct_answers"] if "correct_answers" in session_attr else 0) + " correct and " + str(session_attr["incorrect_answers"] if "incorrect_answers" in session_attr else 0) + " incorrect answers."


def final_speech_text(session_attr):
    final_speech_text = ""
    if session_attr["correct_answers"] > session_attr["incorrect_answers"]:
        final_speech_text = " You won! Great work! Do you want to play again?"
    else:
        final_speech_text = " Better luck next time! Do you want to play again?"

    speech_text = "You have finished this round. " + score_string(session_attr) + final_speech_text
    return speech_text


def check_answer(answer, correct_answer, session_attr):
    trivia = session_attr["trivia"]
    current_question_index = session_attr["current_question_index"]
    if answer.lower() == correct_answer.lower():
        session_attr["correct_answers"] = session_attr["correct_answers"] + 1 
        speech_text = "Great! " + correct_answer + " is the correct answer! "
        if current_question_index == len(trivia["results"]) - 1:
            del session_attr['game_state']
            speech_text = speech_text + final_speech_text(session_attr)
        else:
            speech_text = speech_text + " " + NEXT_QUESTION_STRING
        session_attr["attempts"] = 0
        session_attr["ongoing_question"] = 0
        return speech_text, speech_text, session_attr    

    if session_attr["attempts"] + 1 < MAXIMUM_ATTEMPTS:
        session_attr["attempts"] = session_attr["attempts"] + 1
        speech_text = answer + " is not correct. You have " + str(MAXIMUM_ATTEMPTS - session_attr["attempts"]) + " more attempts left. Please try again."
        return speech_text, speech_text, session_attr
    else:
        session_attr["incorrect_answers"] = session_attr["incorrect_answers"] + 1 
        speech_text = answer + " is not correct. Correct answer is " + correct_answer + ". "
        if current_question_index == len(trivia["results"]) - 1:
            del session_attr['game_state']
            speech_text = speech_text + final_speech_text(session_attr)
        else:
            speech_text = speech_text + " " + NEXT_QUESTION_STRING
        session_attr["ongoing_question"] = 0
        session_attr["attempts"] = 0
        return speech_text, NEXT_QUESTION_STRING, session_attr

@sb.global_response_interceptor()
def log_response(handler_input, response):
    """Response logger."""
    # type: (HandlerInput, Response) -> None
    logger.info("Response: {}".format(response))

    
lambda_handler = sb.lambda_handler()
