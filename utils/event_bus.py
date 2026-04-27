import pika
import json
import logging
import os

logger = logging.getLogger("fagentllm.event_bus")

def publish_event(event_type: str, payload: dict):
    """
    Publish an event to RabbitMQ for causal propagation across systems.
    This fulfills the V3 demo requirement.
    """
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    try:
        parameters = pika.URLParameters(rabbitmq_url)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        channel.exchange_declare(exchange='fagent_events', exchange_type='topic')
        
        message = json.dumps(payload)
        channel.basic_publish(
            exchange='fagent_events',
            routing_key=event_type,
            body=message
        )
        logger.info(f"Published event {event_type} to RabbitMQ")
        connection.close()
    except Exception as e:
        logger.warning(f"Failed to publish event to RabbitMQ: {e}. Ensure RabbitMQ is running.")
