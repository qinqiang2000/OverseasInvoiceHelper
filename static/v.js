// 存储当前上传的文件名
var currentFilename = '';

// 获取当前时间的函数
function getCurrentTime() {
  const now = new Date();
  const hours = now.getHours().toString().padStart(2, '0');
  const minutes = now.getMinutes().toString().padStart(2, '0');
  const seconds = now.getSeconds().toString().padStart(2, '0');
  return `${hours}:${minutes}:${seconds}`;
}

// 打印带有时间戳的日志
function log(...args) {
  const timestamp = getCurrentTime();
  console.log(`[${timestamp}]`, ...args);
}



document.addEventListener('DOMContentLoaded', function () {
  // 获取非模态窗口元素
  var floatWindow = document.getElementById("floatWindow");
  log('获取非模态窗口元素', floatWindow);
  // 获取关闭按钮元素
  var span = document.getElementsByClassName("close")[0];
  // 关闭非模态窗口
  span.onclick = function () {
    floatWindow.style.display = "none";
  }

  var socket = io.connect('http://' + '127.0.0.1' + ':' + '8000');

  socket.on('connect', function () {
    console.log('WebSocket connected!');
    socket.emit('start_data_transfer');  // 告知服务器开始数据传输
  });

  socket.on('progress', function (data) {
    log('Progress: ' + JSON.stringify(data));

    if (data.progress)
      document.getElementById('progressBar').style.width = data.progress + '%';

    if (data.status)
      document.getElementById('progress-status').textContent = data.status;

    // 当进度完成时,隐藏进度条
    if (data.progress >= 100) {
      document.getElementById('progress-container-wrapper').style.display = 'none';
      document.getElementById('progress-status').style.display = 'none';
    }
  });

  socket.on('data', function (data) {
    if (!data.data) return

    document.getElementById('table-container').style.display = 'block';
    createTable(data.data, data.page)
  });

  // 创建表格
  function createTable(data, page) {
    var container = document.getElementById('table-container');

    // 创建一个新的表格
    var table = document.createElement('table');
    table.classList.add('data-table'); // 添加样式类

    // 遍历 JSON 对象
    for (var key in data) {
      if (data.hasOwnProperty(key)) {
        var value = data[key];

        // 创建表格行
        var row = table.insertRow(-1);
        var cellKey = row.insertCell(0);
        var cellValue = row.insertCell(1);
        var cellIcon = row.insertCell(2); // 新增图标列

        cellKey.innerHTML = key;
        cellValue.innerHTML = value;

        // 添加 thumb-down 图标
        cellIcon.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="icon-md"><path fill-rule="evenodd" clip-rule="evenodd" d="M11.8727 21.4961C11.6725 21.8466 11.2811 22.0423 10.8805 21.9922L10.4267 21.9355C7.95958 21.6271 6.36855 19.1665 7.09975 16.7901L7.65054 15H6.93226C4.29476 15 2.37923 12.4921 3.0732 9.94753L4.43684 4.94753C4.91145 3.20728 6.49209 2 8.29589 2H18.0045C19.6614 2 21.0045 3.34315 21.0045 5V12C21.0045 13.6569 19.6614 15 18.0045 15H16.0045C15.745 15 15.5054 15.1391 15.3766 15.3644L11.8727 21.4961ZM14.0045 4H8.29589C7.39399 4 6.60367 4.60364 6.36637 5.47376L5.00273 10.4738C4.65574 11.746 5.61351 13 6.93226 13H9.00451C9.32185 13 9.62036 13.1506 9.8089 13.4059C9.99743 13.6612 10.0536 13.9908 9.96028 14.2941L9.01131 17.3782C8.6661 18.5002 9.35608 19.6596 10.4726 19.9153L13.6401 14.3721C13.9523 13.8258 14.4376 13.4141 15.0045 13.1902V5C15.0045 4.44772 14.5568 4 14.0045 4ZM17.0045 13V5C17.0045 4.64937 16.9444 4.31278 16.8338 4H18.0045C18.5568 4 19.0045 4.44772 19.0045 5V12C19.0045 12.5523 18.5568 13 18.0045 13H17.0045Z" fill="currentColor"></path></svg>';

        var svgElement = cellIcon.querySelector('svg');
        svgElement.setAttribute('page', page);
        svgElement.setAttribute('key', key);
        svgElement.addEventListener('click', function () {
          sendIconClickDataToBackend(this);
        });
      }
    }

    // 创建表格标题
    const title = document.createElement('h3');
    title.textContent = `第 ${page} 页`;
    title.setAttribute('page', page);
    title.addEventListener('click', function () {
      getPageText(this);
    });

    container.appendChild(title);

    // 将表格添加到容器
    container.appendChild(table);
  }

  // 获取后端返回的中间文本
  function getPageText(titleElement) {
    page = titleElement.getAttribute('page');
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/text', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify({ page: page, filename: currentFilename }));
    xhr.onload = function () {
      if (xhr.status === 200) {
        var response = JSON.parse(xhr.responseText);
        if (response.status === 'success') {
          var newWindow = window.open('', '_blank');
          newWindow.document.write('<html><head><title>数据展示</title><style>p { white-space: pre-wrap; }</style></head><body>');
          newWindow.document.write('<h1>数据</h1>');
          newWindow.document.write('<p>' + response.text + '</p>'); // 假设 responseData 是您通过 AJAX 获取的数据
          newWindow.document.write('</body></html>');
          newWindow.document.close();
        } else {
          alert(response.msg);
        }
      } else {
        alert('无法发送data到后台');
      }
    };
  }

  // 发送点击图标的数据到后台 
  function sendIconClickDataToBackend(iconElement) {
    // isClicked=0 表示未点击, 发送到后台已点击状态，并修改图标为已点击颜色;反之亦然
    isClicked = iconElement.classList.contains('icon-clicked')
    var page = iconElement.getAttribute('page');
    var key = iconElement.getAttribute('key');

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/down', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify({ page: page, key: key, clicked: !isClicked, filename: currentFilename }));
    log('发送点击图标的数据到后台', { page: page, key: key, clicked: !isClicked, filename: currentFilename });

    xhr.onload = function () {
      if (xhr.status === 200) {
        var response = JSON.parse(xhr.responseText);
        if (response.status === 'success') {
          console.log('Down data sent to backend successfully');
          iconElement.classList.toggle('icon-clicked');
        } else {
          alert(response.msg);
        }
      } else {
        alert('无法发送data到后台');
      }
    };
  }

  function upload_file(elem) {
    // 检查是否选择了文件
    if (elem.files.length <= 0)
      return

    var file = elem.files[0];
    var formData = new FormData();
    formData.append('file', file);
    log('开始上传文件', file);

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload', true);
    xhr.onload = function () {
      if (xhr.status === 200) {
        console.log(xhr.responseText)

        var response = JSON.parse(xhr.responseText);
        var uploadedFileName = response.filename;
        currentFilename = uploadedFileName;
        log('文件上传成功', uploadedFileName);

        table = document.getElementById("table-container");
        table.innerHTML = ""
        document.getElementById('progress-container-wrapper').style.display = 'block';
        document.getElementById('progress-status').style.display = 'block';

        // 更新 embed 标签的 src 属性
        var pdfViewer = document.getElementById('pdf-viewer');
        var embedTag = '<embed src="/uploads/' + uploadedFileName + '" type="application/pdf" width="100%" height="100%" />';
        pdfViewer.innerHTML = embedTag;

        document.getElementById('second-upload-btn').style.display = 'block';
        document.getElementById('json-viewer').style.display = 'block';

      } else {
        log('文件上传失败');
      }
    };

    xhr.send(formData);
  }

  document.getElementById('file-upload').addEventListener('change', function () {
    upload_file(this)
  });
  document.getElementById('second-file-upload').addEventListener('change', function () {
    upload_file(this)
  });

  var isDragging = false;
  var leftPanel = document.getElementById('pdf-viewer');
  var rightPanel = document.getElementById('json-viewer');
  var gutter = document.getElementById('gutter');
  var container = document.getElementById('container');

  gutter.addEventListener('mousedown', function (e) {
    e.preventDefault();
    isDragging = true;
  });

  document.addEventListener('mousemove', function (e) {
    // Only resize if dragging is active
    if (!isDragging) return;

    var containerRect = container.getBoundingClientRect();
    var leftWidth = e.clientX - containerRect.left;
    var rightWidth = containerRect.right - e.clientX;

    leftPanel.style.width = `${leftWidth}px`;
    rightPanel.style.flexGrow = 1; // 防止右侧面板伸展
  });

  document.addEventListener('mouseup', function (e) {
    isDragging = false;
  });

  document.getElementById('upload-btn').addEventListener('click', function () {
    document.getElementById('file-upload').click();
  });

  document.getElementById('second-upload-btn').addEventListener('click', function () {
    document.getElementById('second-file-upload').click();
  });
});

