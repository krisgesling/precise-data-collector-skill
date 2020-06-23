from mycroft import MycroftSkill, intent_handler
from mycroft.util.parse import extract_number, match_one


class PreciseDataCollector(MycroftSkill):
    def __init__(self):
        MycroftSkill.__init__(self)
        self.consent_confirmed = False
        self.speaker_metadata = {
            'age': None,
            'gender': None,
            'accent': None,
        }
        self.use_count = 0

    def get_intro_message(self):
        self.speak_dialog('introduction')
        self.consent_confirmed = self.confirm_consent()
        if self.consent_confirmed:
            self.speak_dialog('tutorial')

    def confirm_consent(self):
        self.speak_dialog('consent.description')
        response = self.ask_yesno('consent.confirm')
        if response != 'yes':
            self.speak_dialog('consent.declined')
        return response == 'yes'

    @intent_handler('collect.data.intent')
    def handle_data_collection(self, message):
        if not self.consent_confirmed:
            confirm_consent()
        has_metadata = self.request_metadata()
        if not has_metadata:
            return False
        
        metadata = self.speaker_metadata
        filename_base = "{}_{}_{}".format(metadata.gender, metadata.age, metadata.accent)
        


    def request_metadata(self):
        """Request metadata about speaker from user to tag samples with.

        We intentionally don't re-use previous metadata as we want to
        encourage diversity of speakers, not lots of samples from the same
        speaker.
        """
        metadata = self.speaker_metadata
        self.use_count += 1
        if self.use_count <= 3:
            self.speak_dialog('metadata.why')
        # else regular user, don't need to explain why any longer.
        metadata.age = extract_number(self.get_response('metadata.age',
            validator=lambda age: extract_number(age),
            on_fail=lambda age: self.speak_dialog('metadata.error.age', 
                                                  { 'age': age })
            ))
        metadata.gender, conf = self.get_response('metadata.gender',
            validator=lambda gender: self.match_gender_vocab(gender),
            on_fail=lambda gender: self.speak_dialog('metadata.error.gender', 
                                                  { 'gender': gender })
            )
        metadata.accent = self.get_response('metadata.accent',
            validator=lambda accent: accent and len(accent.split()) < 3,
            on_fail=lambda accent: self.speak_dialog('metadata.error.accent', 
                                                  { 'accent': accent })
            )
        return metadata.age and metadata.gender and metadata.accent
    
    def match_gender_vocab(self, utterance):
        match, confidence = match_one(utterance, self.translate_namedvalues('gender'))
        return confidence > 0.5



    def handle_combined_recording(self):
        from precise_runner import PreciseEngine
        engine = PreciseEngine(self.engine_exe, self.model_file,
                               self.chunk_size)
        engine.start()

        recording = self.record_wav()

        with wave.open(recording, 'r') as wr:
            orig_params = wr.getparams()
            frames = wr.readframes(wr.getnframes() - 1)

        ww_positions = self.extract_ww_positions(frames, engine)
        engine.stop()

        samples_folder = join(self.folder, 'samples', name)
        samples_raw_folder = join(samples_folder, 'not-wake-word')
        makedirs(samples_raw_folder, exist_ok=True)
        self.split_recording(frames, samples_raw_folder, ww_positions, orig_params)

        self.speak_dialog('recording.complete')

    def record_wav(self):
        audio_file = resolve_resource_file(
            self.config_core.get('sounds').get('start_listening'))
        if audio_file:
            play_wav(audio_file).wait()

        self.bus.emit(Message('mycroft.mic.mute'))
        try:
            fd, tmp_file = mkstemp('.wav')
            subprocess.Popen(
                ["arecord", "-f", "S16_LE", "-r", str(16000), "-c",
                 str(1), "-d",
                 str(10), tmp_file]).wait()
        finally:
            self.bus.emit(Message('mycroft.mic.unmute'))
        return tmp_file

    def extract_ww_positions(self, frames, engine):
        max_pos = -1
        max_val = float('-inf')
        max_positions = []
        for i in range(self.chunk_size, len(frames) + 1, self.chunk_size):
            chunk = frames[i - self.chunk_size:i]
            prob = engine.get_prediction(chunk)
            self.log.info("PROB: {}".format(prob))
            if prob > self.threshold:
                if prob > max_val:
                    max_val = prob
                    max_pos = i
            else:
                if max_pos >= 0:
                    max_positions.append((max_pos, i))
                    max_pos = -1
                    max_val = float('-inf')
        if max_pos >= 0:
            max_positions.append((max_pos, len(frames)))
        return max_positions

    def split_recording(self, frames, folder, positions, params):
        prev_pos = 0
        for pos, end_pos in positions:
            data = frames[prev_pos:end_pos]
            prev_pos = end_pos
            sample_file = join(folder, 'sample-{}.wav'.format(pos))
            with wave.open(sample_file, 'wb') as wf:
                wf.setparams(params)
                wf.writeframes(data)


def create_skill():
    return PreciseDataCollector()

