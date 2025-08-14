def save_buffer(self):
    if not self.buffer or self.valid_chunk_count < MIN_VALID_CHUNKS:
        self.reset()
        return False
    
    total_samples = sum(len(chunk) for chunk in self.buffer)
    duration = total_samples / SAMPLE_RATE
    
    if MIN_AUDIO_DURATION <= duration <= MAX_AUDIO_DURATION:
        # [Previous audio processing code remains the same until API calls]
        if self.silence_start and self.last_active_time:
            keep_duration = (self.last_active_time - self.recording_start_time) + 0.5
            keep_samples = int(keep_duration * SAMPLE_RATE)
            
            trimmed_buffer = []
            accumulated_samples = 0
            
            for chunk in self.buffer:
                if accumulated_samples + len(chunk) <= keep_samples:
                    trimmed_buffer.append(chunk)
                    accumulated_samples += len(chunk)
                else:
                    remaining = keep_samples - accumulated_samples
                    if remaining > 0:
                        trimmed_buffer.append(chunk[:remaining])
                    break
            
            final_audio = np.concatenate(trimmed_buffer, axis=0)
        else:
            final_audio = np.concatenate(self.buffer, axis=0)
        
        final_rms = self.calculate_rms(final_audio)
        if final_rms < SILENCE_THRESHOLD:
            self.reset()
            return False
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        file_name = f"{SAVE_DIR}/audio_{timestamp}.wav"
        
        with wave.open(file_name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(final_audio.tobytes())
        
        print(f"✅ Audio saved as {file_name} (Duration: {duration:.2f}s)")
        t_start = time.time()
        
        # Notify client that processing is starting
        sio.emit('processing_started', room=current_sid)
        processing_states[current_sid] = True
        
        # Process the audio
        transcription = send_to_speech_api(file_name)
        if transcription:
            print(f"📝 Transcription received: {transcription}")
            answer = send_to_rag_api(transcription)
            if answer:
                print(answer)
                download_url = send_to_tts_api(answer)
                if download_url:
                    file_name = os.path.basename(download_url)
                    audio_response = requests.get(download_url)
                    if audio_response.status_code == 200:
                        with open(file_name, "wb") as file:
                            file.write(audio_response.content)
                        t_end = time.time()
                        t_taken = t_end - t_start
                        print("✅ Time taken:", t_taken)
                        playsound(file_name)
                        # Notify client that processing is complete
                        sio.emit('processing_complete', room=current_sid)
                        processing_states[current_sid] = False
                    else:
                        print("❌ Failed to download audio file")
                        sio.emit('processing_error', room=current_sid)
                        processing_states[current_sid] = False
                else:
                    print("❌ Download URL not found in response")
                    sio.emit('processing_error', room=current_sid)
                    processing_states[current_sid] = False
            else:
                print("❌ Answer not found from LLM response")
                sio.emit('processing_error', room=current_sid)
                processing_states[current_sid] = False
                
        else:
            print("❌ Error Generating Transcription")
            sio.emit('processing_error', room=current_sid)
            processing_states[current_sid] = False
        
        self.reset()
        return True
        
    self.reset()
    return False