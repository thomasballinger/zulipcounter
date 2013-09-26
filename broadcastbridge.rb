require 'pusher-client'
require 'net/http'
require 'net/https'
require 'uri'
require 'nokogiri'
require 'json'

Zulip_bot_email = ENV['FACULTY_ZULIP_BOT_EMAIL']
Zulip_bot_api_key = ENV['FACULTY_ZULIP_BOT_API_KEY']

m = /http:\/\/([a-z0-9]+):([a-z0-9]+)@api.pusherapp.com\/apps\/([0-9]+)/.match ENV['TEST_PUSHER_URL']
TestPusherUser = m[1]
TestPusherSecret = m[2]

def send_zulip_msg(msg)
  uri = URI.parse('https://api.zulip.com/v1/messages')

  https = Net::HTTP.new(uri.host, uri.port) 
  https.use_ssl = true

  req = Net::HTTP::Post.new(uri.path)
  req.basic_auth Zulip_bot_email, Zulip_bot_api_key
  req.set_form_data(type: 'stream',
                    to: 'bot-test',
                    subject: 'broadcasts',
                    content: msg)
  res = https.request(req)
end

PusherClient.logger = Logger.new(STDOUT)

class Broadcast
  attr_reader :html
  def initialize(data)
    puts data
    puts data.class
    @id = data[:id]
    @person_id = data[:person_id]
    @client_id = data[:client_id]
    @html = Nokogiri::HTML(data[:html])
  end
  def name
    @html.css('a')[1].inner_text
  end
  def content
    @html.css('.text').inner_text.strip
  end
end

#TODO parse these from ENV
options = {:secret => TestPusherSecret} 
socket = PusherClient::Socket.new(TestPusherUser, options)

socket.subscribe('private-latest-broadcasts')

socket.bind('new-broadcast') do |data|
  b = Broadcast.new JSON.parse(data, :symbolize_names => true)
  send_zulip_msg "#{b.content} - #{b.name}"
end

puts send_zulip_msg('starting to listen for broadcasts...')
socket.connect
#b = Broadcast.new({id: 1, person_id: 2, client_id: 3, html: %(<li class='row' id='38'>\n <div class='photo-and-text-container'>\n <div class='photo'>\n <a href=\"/people/53\"><img alt=\"Thomas_ballinger_75\" height=\"64\" src=\"/assets/people/thomas_ballinger_75.jpg\" width=\"64\" /></a>\n </div>\n <div class='container'>\n <span class='date'>\n 0m\n </span>\n <div class='name'>\n <a href=\"/people/53\">Tom Ballinger</a>\n </div>\n <div class='text'>\n test\n </div>\n </div>\n </div>\n <span class='edit-controls'>\n <a href=\"/broadcasts/38\" data-confirm=\"Are you sure you want to delete this broadcast?\" data-method=\"delete\" rel=\"nofollow\"><img alt=\"Trash\" src=\"/assets/trash.png\" /></a>\n </span>\n</li>\n')})
#puts b.name
