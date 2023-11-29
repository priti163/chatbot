import json
from channels import Channel,Group
from django.contrib.auth import get_user_model
from chat.models import ChatMessage
from .jwt_decorators import jwt_request_parameter, jwt_message_text_field
from django import forms
from botlogic.Lina.Lina import callBot,edit_real_time

def chat_history_api(message):
    print ("chat_history_api")
    msg = message.content['message']
    msg_id = message.content['msg_id']
    userId = message.content['userId']
    user = get_user_model().objects.get(pk=userId)    
    field = forms.CharField()
    if not (field.clean(msg)):
        raise forms.ValidationError("Message can not be empty")
    msg = field.clean(msg)

    msg_obj = ChatMessage.objects.get(pk=msg_id)

    if(msg_obj.lineId):
        print "edit_realtime_history"
        reply_type = "message"
        reply_msg = edit_real_time(msg, msg_obj.character, msg_obj.lineId)

        msg_obj.message = msg_obj.message.split('\nNew reply:')[-1] + '\n' + reply_msg
        msg_obj.save()
        
    else:
        print "intent_history"
        reply_type = "intent"
        msg_obj.message = msg
        msg_obj.save()
                    
    if(msg_obj):
            final_msg = {
                    "user":msg_obj.user.username,
                    "msg": msg_obj.message,
                    "owner": msg_obj.owner,
                    "type":reply_type,
                    "data":None,
                    "line_id":msg_obj.lineId,
                    "msg_id":msg_obj.id,
                    "timestamp":msg_obj.formatted_timestamp,
                    "formated_timestamp":msg_obj.formatted_timestamp_milliseconds
            }
    else:
        final_msg = {
            "user":user.username,
            "msg": "sorry ,DB error",
            "owner": "bot",    
        }    
    print("final_msg",final_msg)    
    # Broadcast to listening socket(send user message to the user himself)
    message.reply_channel.send({"text": json.dumps(final_msg)})    

def chat_send_api(message):
    print("chat_send_api")
    owner = "user"
    userId = message.content['userId']
    user = get_user_model().objects.get(pk=userId)
    msg = message.content['message']     
    field = forms.CharField()
    if not (field.clean(msg)):
        raise forms.ValidationError("Message can not be empty")
    msg = field.clean(msg)     
    # Save to model
    msg_obj = ChatMessage.objects.create(
        user = user,
        message = msg,
        owner = owner
    )
    if(msg_obj):
        final_msg = {
            "user":msg_obj.user.username,
            "msg": msg_obj.message,
            "owner": msg_obj.owner,
            "timestamp":msg_obj.formatted_timestamp,#formatted_timestamp
            "formated_timestamp":msg_obj.formatted_timestamp_milliseconds#timestamp_millisec
        }
    else:
        final_msg = {
            "user":user.username,
            "msg": "sorry ,DB error",
            "owner": owner,    
        }    
    print("final_msg",final_msg)
    # Broadcast to listening socket(send user message to the user himself)
    message.reply_channel.send({"text": json.dumps(final_msg)})

    #bot listening logic
    payload = {
        'reply_channel': message.content['reply_channel'],
        'message': msg,
        'userId': user.id,
        'character': message.content['character']
    }
    Channel("bot-api.receive").send(payload)


# Connected to bot.receive channel
# bot_send is bot.receive channel consumer
# bot consumer 
def bot_send_api(message):
    print("bot_send_api")
    owner = "bot"
    userId = message.content['userId']
    user = get_user_model().objects.get(pk=userId)
    msg = message.content['message']  
    character = message.content['character']
    #bot logic
    response_type,response =callBot(msg,character)
    if(response_type=="message"):
        msg = response[0]
        dataset_number = response[1]
        line_id = response[2]
    elif(response_type=="intent"):
        msg = ""
        dataset_number = None
        line_id = None
        
           

    msg_obj = ChatMessage.objects.create(
        user = user,
        message = msg,
        owner = owner,
        lineId = line_id,
        character = dataset_number
    )


    if(msg_obj):
        final_msg = {
                "user":msg_obj.user.username,
                "msg": msg_obj.message,
                "owner": msg_obj.owner,
                "type":response_type,
                "data":response,
                "line_id":msg_obj.lineId,
                "msg_id":msg_obj.id,
                "timestamp":msg_obj.formatted_timestamp,
                "formated_timestamp":msg_obj.formatted_timestamp_milliseconds
        }
        
    else:
        final_msg = {
            "user":user.username,
            "msg": "sorry ,DB error",
            "owner": owner,    
        }  
    print("final_msg",final_msg)
    # Broadcast to listening socket(send bot reply message to the user)
    message.reply_channel.send({"text": json.dumps(final_msg)})





# Connected to websocket.connect
@jwt_request_parameter
def ws_connect_api(message):
    print("ws_connect_api")
    # Accept connection
    message.reply_channel.send({"accept": True})
    #add each user to all-users group when they connect,
    #so that they can recieve any bot announce message. 
    Group("all-users").add(message.reply_channel)

# Connected to websocket.receive
@jwt_message_text_field
def ws_receive_api(message):
    payload = json.loads(message['text'])
    payload['reply_channel'] = message.content['reply_channel']
    payload['userId'] = message.user.id
    print("ws_receive_api",payload)
    # Stick the message onto the processing queue
    Channel("chat-api.receive").send(payload)

# Connected to websocket.disconnect
def ws_disconnect_api(message):
    print("ws_disconnect_api")
    #remove each user from all-users group when they disconnect.
    Group("all-users").discard(message.reply_channel)




