import argparse
import asyncio
import json
import logging
import ssl
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaBlackhole, MediaRecorder

import cv2
import numpy as np
from av import VideoFrame

logging.basicConfig(level=logging.INFO)

pcs = set()

class ScreenVideoTrack(VideoStreamTrack):
    """
    VideoStreamTrack that captures the screen using OpenCV.
    """

    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)  # Kamera yerine ekran yakalamak için değiştirebiliriz.

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        ret, frame = self.cap.read()
        if not ret:
            # Siyah frame döndür
            img = np.zeros((480, 640, 3), dtype=np.uint8)
        else:
            img = frame

        video_frame = VideoFrame.from_ndarray(img, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

async def index(request):
    content = open("client.html", "r").read()
    return web.Response(content_type="text/html", text=content)

async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    # Ekran yayını yerine kamera yayını var, ama bunu OpenCV ile ekran yakalamaya uyarlayabilirsin.
    pc.addTrack(ScreenVideoTrack())

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response(
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    )

async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC Screen Share Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to listen on")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_post("/offer", offer)

    web.run_app(app, host=args.host, port=args.port)
