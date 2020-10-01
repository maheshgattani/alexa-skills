# -*- coding: utf-8 -*-

# This is a High Low Guess game Alexa Skill.
# The skill serves as a simple sample on how to use the
# persistence attributes and persistence adapter features in the SDK.
import random
import logging
import os
import boto3

from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model import Response
from ask_sdk_s3.adapter import S3Adapter

SKILL_NAME = 'My recipe'
bucket_name = os.environ.get('S3_PERSISTENCE_BUCKET')
s3_client = boto3.client('s3',
                         region_name=os.environ.get('S3_PERSISTENCE_REGION'),
                         config=boto3.session.Config(signature_version='s3v4',s3={'addressing_style': 'path'}))
s3_adapter = S3Adapter(bucket_name=bucket_name, path_prefix="Media", s3_client=s3_client)
sb = CustomSkillBuilder(persistence_adapter=s3_adapter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

GREETINGS_PROMPT = "Hello! You can ask me for ingredients and recipes of your favorite cocktails."
RECIPE_START_PROMPT = "Here are the ingredients for your {} recipe: "
MISSING_RECEIPT_PROMPT = "Sorry I do not know the recipe for {}. You can ask me for other recipes like Manhattan or Old Fashined."
MISSING_INGREDIENT_PROMPT = "There is no {} in the recipe for {}."
FAILURE_PROMPT = "Sorry I could not understand that. Say help to continue!"
HELP_PROMPT = "I have a collection of your favorite cocktails. You can ask me for the ingredients and recipes!"
REPEAT_PROMPT = "You are making a {}. If you want a different drink, say Cancel. If you want me to repeat the Manhattan recipe, say Repeat."
INGREDIENT_PROMPT = "You need {} of {}."
GARNISH_PROMPT = "You need {} as garnish."

RECIPES = {
    "manhattan": {
        "ingredients": {
            "whiskey": {
                "quantity": "2 ounces",
                "brand": "XYZ",
                "type": "Rye"
            },
            "vermouth": {
                "quantity": "1 ounces",
                "brand": "XYZ",
                "type": "sweet"
            },
            "bitters": {
                "quantity": "2 dashes",
            }
        },
        "garnishes" : ["cherry"],
        "liquors": ["whiskey"],
        "recipe": "Mix the whiskey, vermouth and bitters in a whiskey glass and stir with some ice. Serve with a cherry on top."
    },
    "old-fashioned": {
        "ingredients": {
            "whiskey": {
                "quantity": "2 ounces",
                "type": "Rye"
            }, 
            "sugar": {
                "quantity": "half teaspoon",
            },
            "bitters": {
                "quantity": "3-4 dashes",
            }
        },
        "garnishes" : ["cherry", "orange slice"],
        "liquors": ["whiskey"],
        "recipe": "Muddle the sugar and bitters in a whiskey glass. Add the whiskey. Serve with ice, cherry and orange slice."
    },
    "gin sling": {
        "ingredients": {
            "gin": {
                "quantity": "one and a half ounces",
            }, 
            "sweet vermouth": {
                "quantity": "1 ounces",
            },
            "lemon juice": {
                "quantity": "three fourth ounces",
            },
            "simple syrup": {
                "quantity": "1 ounces",
            },
            "soda water": {
                "quantity": "3-4 ounces",
            },
            "bitters": {
                "quantity": "2 dashes",
            }
        },
        "garnishes" : ["lemon spiral"],
        "liquors": ["gin"],
        "recipe": "Shake everything except the soda water in a shaker with ice. Serve with ice and soda water."
    },
    "bee's knees": {
        "ingredients": {
            "gin": {
                "quantity": "2 ounces",
            }, 
            "lemon juice": {
                "quantity": "three fourth ounces",
            },
            "honey syrup": {
                "quantity": "half ounces",
            },
        },
        "garnishes" : ["lemon twist"],
        "liquors": ["gin"],
        "recipe": "Shake everything in a shaker with ice. Serve with lemon twist."
    },
    "gimlet": {
        "ingredients": {
            "gin": {
                "quantity": "two and half ounces",
            }, 
            "lime juice": {
                "quantity": "half ounces",
            },
            "simple syrup": {
                "quantity": "half ounces",
            },
        },
        "garnishes" : ["lime twist"],
        "liquors": ["gin"],
        "recipe": "Shake everything in a shaker with ice. Serve with lime twist."
    },
    "mojito": {
        "ingredients": {
            "white rum": {
                "quantity": "one and half ounces",
            }, 
            "lime juice": {
                "quantity": "one and a quarter ounces",
            },
            "sugar": {
                "quantity": "one teaspoon",
            },
            "soda water": {
                "quantity": "4 ounces",
            },
            "mint leafs": {
                "quantity": "one ounce",
            }
        },
        "liquors": ["white rum"],
        "recipe": "Muddle the mint with lime juice in the bottom of a tail cocktail glass. Add the rum, sugar, crushed ice and soda. Cover and shake. Serve with a lime wedge"
    },
    "espresso martini": {
        "ingredients": {
            "vodka": {
                "quantity": "two ounces",
            }, 
            "simple syrup": {
                "quantity": "half ounces",
            },
            "coffee liqueur": {
                "quantity": "half ounces",
            },
            "cold brew concentrate": {
                "quantity": "1 ounces",
            },
            "milk": {
                "quantity": "half ounce",
            }
        },
        "garnishes" : ["coffee beans"],
        "liquors": ["vodka"],
        "recipe": "Mix and shake all the ingredients. Serve with coffee beans on top."
    },
    "margarita": {
        "ingredients": {
            "vodka": {
                "quantity": "two ounces",
            }, 
            "lime juice": {
                "quantity": "one ounces",
            },
            "simple syrup": {
                "quantity": "half ounces",
            },
            "watermelon juice": {
                "quantity": "three fourth ounces",
            },
            "orange liqueur": {
                "quantity": "half ounces",
            },
        },
        "liquors": ["vodka"],
        "recipe": "Muddle a pepper with the lime juice. Then mix and shake rest of the ingredients. Serve with a salt rim on the glass."
    },
    "caipirinha": {
        "ingredients": {
            "cachaca": {
                "quantity": "2 ounces",
            }, 
            "sugar": {
                "quantity": "one teaspoon",
            },
            "lime": {
                "quantity": "3-6 wedges",
            },
        },
        "liquors": ["cachaca"],
        "recipe": "Squeeze the lime wedges and sugar together with a spoon and then add the cachaca. Serve in a manhattan glass."
    },
}

def text_for_recipe(cocktail, ingredients_only):
    ingredients = RECIPES[cocktail]['ingredients']
    garnishes = RECIPES[cocktail]['garnishes'] if 'garnishes' in RECIPES[cocktail] else []
    recipe = RECIPES[cocktail]['recipe']
    text = RECIPE_START_PROMPT.format(cocktail)
    for ingredient, details in ingredients.items():
        text = text + details["quantity"] + ' of ' + ingredient + ', '
    for garnish in garnishes:
        text = text + garnish + ' and '
    if len(garnishes) != 0:
        text = text[:-4]
        text = text + " as garnish"
    else:
        text = text[:-2]
    
    text = text + '. '
    
    if not ingredients_only:
        text = text + recipe
    
    return text

def launch(handler_input, ingredients_only = False):
    attr = handler_input.attributes_manager.persistent_attributes
    cocktail = None
    try: 
        cocktail = handler_input.request_envelope.request.intent.slots["cocktail"].value
        cocktail = cocktail.lower()
        if not cocktail and attr and attr['ongoing_recipe'] is not None:
            cocktail = attr['ongoing_recipe']
    except:
        coctail = None
    
    if not cocktail:
        return GREETINGS_PROMPT

    if cocktail not in RECIPES:
        return MISSING_RECEIPT_PROMPT.format(cocktail)

    if not attr:
        attr['ongoing_recipe'] = cocktail

    handler_input.attributes_manager.session_attributes = attr

    return text_for_recipe(cocktail, ingredients_only)

def quanity_for_ingredient(handler_input):
    attr = handler_input.attributes_manager.session_attributes
    ingredient = None
    try:
        ingredient = handler_input.request_envelope.request.intent.slots["ingredient"].value
        ingredient = ingredient.lower()
    except:
        ingredient = None

    if not ingredient:
        return FAILURE_PROMPT

    cocktail = None
    try:
        cocktail = handler_input.request_envelope.request.intent.slots["cocktail"].value
        cocktail = cocktail.lower()
    except:
        if attr and 'ongoing_recipe' in attr:
            cocktail = attr['ongoing_recipe']
        if cocktail is None:
            return FAILURE_PROMPT
    
    if ingredient == "liquor":
        liquors = RECIPES[cocktail]['liquors']
        speech_text = ""
        for liquor in liquors:
            speech_text = speech_text + INGREDIENT_PROMPT.format(RECIPES[cocktail]['ingredients'][liquor]["quantity"], liquor)
        return speech_text
        
    if ingredient not in RECIPES[cocktail]['ingredients'] and ingredient not in RECIPES[cocktail]['garnishes']:
        return MISSING_INGREDIENT_PROMPT.format(ingredient, cocktail)
    
    if ingredient in RECIPES[cocktail]['ingredients']:
        return INGREDIENT_PROMPT.format(RECIPES[cocktail]['ingredients'][ingredient]["quantity"], ingredient)
    
    if ingredient in RECIPES[cocktail]['garnishes']:
        return GRARNISH_PROMPT.format(ingredient)

def list_cocktails():
    text = 'Here are your favorite cocktails: '
    for cocktail, details in RECIPES.items():
        text = text + cocktail + ', '
    text = text[:-2]
    text = text + "."
    return text + " You can ask me the recipe for any of them."

@sb.request_handler(can_handle_func=is_request_type("LaunchRequest"))
def launch_request_handler(handler_input):
    """Handler for Skill Launch.

    Get the persistence attributes, to figure out the skill state.
    """
    # type: (HandlerInput) -> Response
    speech_text = launch(handler_input)
    reprompt = speech_text
    
    attr = handler_input.attributes_manager.session_attributes
    attr["last_response"] = speech_text
    handler_input.attributes_manager.session_attributes = attr

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("AMAZON.HelpIntent"))
def help_intent_handler(handler_input):
    """Handler for Help Intent."""
    # type: (HandlerInput) -> Response
    speech_text = HELP_PROMPT
    reprompt = speech_text

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_intent_name("RecipeIntent"))
def recipe_intent_handler(handler_input):
    """Handler for Recipe Intent."""
    # type: (HandlerInput) -> Response
    speech_text = launch(handler_input)
    reprompt = speech_text

    attr = handler_input.attributes_manager.session_attributes
    attr["last_response"] = speech_text
    handler_input.attributes_manager.session_attributes = attr

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_intent_name("IngredientIntent"))
def ingredient_intent_handler(handler_input):
    """Handler for Ingredient Intent."""
    # type: (HandlerInput) -> Response
    speech_text = launch(handler_input, True)
    reprompt = speech_text

    attr = handler_input.attributes_manager.session_attributes
    attr["last_response"] = speech_text
    handler_input.attributes_manager.session_attributes = attr

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("QuantityIntent"))
def quantity_intent_handler(handler_input):
    """Handler for Quantity Intent."""
    # type: (HandlerInput) -> Response
    speech_text = quanity_for_ingredient(handler_input)
    reprompt = speech_text

    attr = handler_input.attributes_manager.session_attributes
    attr["last_response"] = speech_text
    handler_input.attributes_manager.session_attributes = attr

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_intent_name("ListIntent"))
def quantity_intent_handler(handler_input):
    """Handler for List Intent."""
    # type: (HandlerInput) -> Response
    speech_text = list_cocktails()
    reprompt = speech_text

    attr = handler_input.attributes_manager.session_attributes
    attr["last_response"] = speech_text
    handler_input.attributes_manager.session_attributes = attr

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_intent_name("AMAZON.RepeatIntent"))
def repeat_intent_handler(handler_input):
    attr = handler_input.attributes_manager.session_attributes
    speech_text = None
    if "last_response" in attr:
        speech_text = attr["last_response"]
    else:
        speech_text = HELP_PROMPT
    reprompt = speech_text

    attr["last_response"] = speech_text
    handler_input.attributes_manager.session_attributes = attr

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


@sb.request_handler(
    can_handle_func=lambda input:
        is_intent_name("AMAZON.CancelIntent")(input) or
        is_intent_name("AMAZON.StopIntent")(input))
def cancel_and_stop_intent_handler(handler_input):
    """Single handler for Cancel and Stop Intent."""
    # type: (HandlerInput) -> Response
    speech_text = "Thank you!"

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


def ongoing_recipe(handler_input):
    """Function that acts as can handle for game state."""
    # type: (HandlerInput) -> bool
    session_attr = handler_input.attributes_manager.session_attributes

    if ("ongoing_recipe" in session_attr
            and session_attr['ongoing_recipe']):
        return True

    return False

@sb.request_handler(can_handle_func=lambda input: True)
def unhandled_intent_handler(handler_input):
    """Handler for all other unhandled requests."""
    # type: (HandlerInput) -> Response
    logger.info("unhandled intent")
    handler_input.response_builder.speak(FAILURE_PROMPT).ask(FAILURE_PROMPT)
    return handler_input.response_builder.response


@sb.exception_handler(can_handle_func=lambda i, e: True)
def all_exception_handler(handler_input, exception):
    """Catch all exception handler, log exception and
    respond with custom message.
    """
    # type: (HandlerInput, Exception) -> Response
    logger.error(exception, exc_info=True)
    speech = "Sorry there was a problem with the skill. We are working on fixing it. Please try again in some time. "
    handler_input.response_builder.speak(speech).ask(speech)
    return handler_input.response_builder.response


@sb.global_response_interceptor()
def log_response(handler_input, response):
    """Response logger."""
    # type: (HandlerInput, Response) -> None
    logger.info("Response: {}".format(response))


lambda_handler = sb.lambda_handler()
