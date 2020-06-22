from mycroft import MycroftSkill, intent_file_handler


class PreciseDataCollector(MycroftSkill):
    def __init__(self):
        MycroftSkill.__init__(self)

    @intent_file_handler('collector.data.precise.intent')
    def handle_collector_data_precise(self, message):
        self.speak_dialog('collector.data.precise')


def create_skill():
    return PreciseDataCollector()

