from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.identity import DefaultAzureCredential
import time

FULLY_QUALIFIED_NAMESPACE = "usg-service-bus.servicebus.windows.net"
QUEUE_NAME = "tx-queue"

credential = DefaultAzureCredential(
    interactive_browser_tenant_id="b878f0fd-d852-47ed-a33a-16a20e00bdfb",
    exclude_interactive_browser_credential=False
)

with ServiceBusClient(FULLY_QUALIFIED_NAMESPACE, credential) as client:

    with client.get_queue_sender(QUEUE_NAME) as sender1:
        sender1.send_messages(
            ServiceBusMessage("test1")
        )
    with client.get_queue_sender(QUEUE_NAME) as sender2:
        sender2.send_messages(
            ServiceBusMessage("test2")
        )

    with client.get_queue_receiver(QUEUE_NAME) as receiver1:
        message1 = receiver1.receive_messages()[0]
        with client.get_queue_receiver(QUEUE_NAME) as receiver2:
            peek_messages1 = receiver2.peek_messages(
                max_message_count=20
            )
            message2 = receiver2.receive_messages()[0]
            time.sleep(0.5)
            peek_messages2 = receiver2.peek_messages(max_message_count=20)
            receiver2.complete_message(message2)
            time.sleep(0.5)
            peek_messages2_5 = receiver2.peek_messages(max_message_count=20)
        receiver1.abandon_message(message1)
    with client.get_queue_receiver(QUEUE_NAME) as receiver3:
        peek_messages3 = receiver3.peek_messages(max_message_count=20)
    with client.get_queue_receiver(QUEUE_NAME) as receiver4:
        message3 = receiver4.receive_messages(max_message_count=20)[0]
        receiver4.complete_message(message3)

        time.sleep(0.5)
        peek_messages4 = receiver4.peek_messages()

    print("Message 1:", message1)
    print("Peek Message 1:\n\t", '\n\t'.join([repr(msg) for msg in peek_messages1]), sep="")
    print("Message 2:", message2)
    print("Peek Message 2:\n\t", '\n\t'.join([repr(msg) for msg in peek_messages2]), sep="")
    print("Peek Message 2.5:\n\t", '\n\t'.join([repr(msg) for msg in peek_messages2_5]), sep="")
    print("Peek Message 3:\n\t", '\n\t'.join([repr(msg) for msg in peek_messages3]), sep="")
    print("Message 3:", message3)
    print("Peek Message 4:\n\t", '\n\t'.join([repr(msg) for msg in peek_messages4]), sep="")
