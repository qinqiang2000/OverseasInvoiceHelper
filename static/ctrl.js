document.addEventListener('keydown', function (event) {
    if (event.ctrlKey && !isNaN(event.key)) {
        // 检测到 Control + 数字
        sendSwitchChannelRequest(event.key);
    }
});

function sendSwitchChannelRequest(channelNumber) {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/switch_channel', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify({ channel: channelNumber }));

    xhr.onload = function () {
        if (xhr.status === 200) {
            var response = JSON.parse(xhr.responseText);
            if (response.status === 'success') {
                alert(response.msg);
            }
            else {
                alert('请求失败：' + xhr.responseText);
            }
        } else {
            alert('请求失败：', xhr.responseText);
        }
    };
}
