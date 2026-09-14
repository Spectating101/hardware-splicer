`timescale 1ns/1ps

module tb_w25q_readonly_reference;
    reg cs_n;
    reg sclk;
    reg mosi;
    wire miso;
    reg [23:0] captured;
    integer i;

    hs_w25q_readonly_reference dut (
        .cs_n(cs_n),
        .sclk(sclk),
        .mosi(mosi),
        .miso(miso)
    );

    task clock_command_bit;
        input bit_value;
        begin
            mosi = bit_value;
            #5 sclk = 1'b1;
            #5 sclk = 1'b0;
        end
    endtask

    task send_byte;
        input [7:0] value;
        integer bit_index;
        begin
            for (bit_index = 7; bit_index >= 0; bit_index = bit_index - 1)
                clock_command_bit(value[bit_index]);
        end
    endtask

    task read_response_bit;
        output bit_value;
        begin
            #5 sclk = 1'b1;
            #1 bit_value = miso;
            #4 sclk = 1'b0;
        end
    endtask

    initial begin
        cs_n = 1'b1;
        sclk = 1'b0;
        mosi = 1'b0;
        captured = 24'h000000;
        #10;

        // Positive reference: 0x9F returns the frozen derived JEDEC reference identity.
        cs_n = 1'b0;
        send_byte(8'h9F);
        for (i = 23; i >= 0; i = i - 1)
            read_response_bit(captured[i]);
        cs_n = 1'b1;
        #10;

        if (captured !== 24'hEF6018) begin
            $display("HS_JEDEC_ID_FAIL=%06h", captured);
            $fatal(1);
        end
        $display("HS_JEDEC_ID=EF6018");

        // Negative reference: WREN is a mutating command and must not expose a response.
        captured = 24'hFFFFFF;
        cs_n = 1'b0;
        send_byte(8'h06);
        for (i = 23; i >= 0; i = i - 1)
            read_response_bit(captured[i]);
        cs_n = 1'b1;
        #10;

        if (captured !== 24'h000000) begin
            $display("HS_MUTATING_REJECT_FAIL=%06h", captured);
            $fatal(1);
        end
        $display("HS_MUTATING_REJECTED=1");
        $finish;
    end
endmodule
