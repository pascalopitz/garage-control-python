#!/usr/bin/env python3
import os
import json
import sys
import traceback
import RPi.GPIO as GPIO

import datetime as dt

import asyncio
import sys

import aiobotocore
import botocore.exceptions

from dotenv import load_dotenv

load_dotenv()

# Set up GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.setup(24, GPIO.OUT)
GPIO.output(24, GPIO.HIGH)

GPIO.setup(25, GPIO.OUT)
GPIO.output(25, GPIO.HIGH)


QUEUE_URL = os.getenv('QUEUE_URL')
S3_BUCKET = os.getenv('S3_BUCKET')

# from https://fredrikaverpil.github.io/2017/06/20/async-and-await-with-subprocesses/
async def run_command(*args):
    """Run command in subprocess.

    Example from:
        http://asyncio.readthedocs.io/en/latest/subprocess.html
    """
    # Create subprocess
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    # Status
    print("Started: %s, pid=%s" % (args, process.pid), flush=True)

    # Wait for the subprocess to finish
    stdout, stderr = await process.communicate()

    # Progress
    if process.returncode == 0:
        print(
            "Done: %s, pid=%s"
            % (args, process.pid),
            flush=True,
        )
    else:
        print(
            "Failed: %s, pid=%s"
            % (args, process.pid),
            flush=True,
        )

    # Result
    result = stdout

    # Return stdout
    return result

async def takeAndStorePicture(session, name):
    async with session.create_client('s3') as s3:
        result = await run_command(*['fswebcam', '-q', '--rotate', '180', '-r', '640x360', '--jpeg', '80', '--timestamp', '%D %T (%Z)', '-'])

        upload = await  s3.put_object(
            Body=result,
            Key=name,
            Bucket=S3_BUCKET,
            ACL='public-read'
        )

        print("Uploaded: " + name)
        print(upload)


async def handleMessage(session, msg):
    if msg == 'photo':
        await takeAndStorePicture(session, 'after.jpg')
    else:
        asyncio.ensure_future(takeAndStorePicture(session, 'before.jpg'))
        await relayOnOff(msg)
        await asyncio.sleep(15)
        asyncio.ensure_future(takeAndStorePicture(session, 'after.jpg'))


async def relayOnOff(side):
    if side == 'left':
        channel = 24

    if side == 'right':
        channel = 25

    GPIO.output(channel, GPIO.LOW)
    await asyncio.sleep(2)
    GPIO.output(channel, GPIO.HIGH)


async def handle(session, client, message):
    try:
        print("Message handle:" + message["Body"])
        j = json.loads(message["Body"])
        await handleMessage(session, j['Message'])

        # Need to remove msg from queue or else it'll reappear
        await client.delete_message(
            QueueUrl=QUEUE_URL,
            ReceiptHandle=message['ReceiptHandle']
        )

        print("Message finished:" + message["Body"])

    except Exception:
        traceback.print_exc(file=sys.stdout)
        raise


async def go(loop):
    # Boto should get credentials from ~/.aws/credentials or the environment
    session = aiobotocore.get_session()
    async with session.create_client('sqs') as client:
        print('Pulling messages off the queue')

        while True:
            try:
                # This loop wont spin really fast as there is
                # essentially a sleep in the receive_message call
                response = await client.receive_message(
                    QueueUrl=QUEUE_URL,
                    WaitTimeSeconds=20,
                )

                if 'Messages' in response:
                    for message in response['Messages']:
                        print("Message received:" + message["Body"])
                        asyncio.ensure_future(handle(session, client, message))

                else:
                    print('No messages in queue')
            except KeyboardInterrupt:
                break

        print('Finished')


def main():
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(go(loop))

    except KeyboardInterrupt:
        pass

    GPIO.cleanup()
    sys.exit(0)



if __name__ == '__main__':
    main()
